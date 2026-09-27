"""
Thin wrapper around spotipy that implements the PRD's Spotify integration
requirements (section 11) and track identification approach (section 12).

Track identification strategy
------------------------------
The Spotify Web API cannot see what your mouse is hovering over inside the
desktop app — there is no such endpoint. The reliable, well-supported signal
is "what is currently playing" (GET /v1/me/player/currently-playing). The
normal workflow this app is built for is: a song is playing -> you decide
you like/dislike it -> you press a shortcut. This avoids depending on
fragile Windows UI Automation / accessibility-tree scraping of Spotify's
window, which breaks whenever Spotify updates its UI.
"""

import re

import spotipy
from spotipy.oauth2 import SpotifyPKCE

from auth import KeyringCacheHandler

# Scopes: only what the PRD actually needs (principle of least privilege,
# section 18).
SCOPE = (
    "playlist-modify-public "
    "playlist-modify-private "
    "playlist-read-private "
    "playlist-read-collaborative "
    "user-read-currently-playing "
    "user-read-playback-state"
)


class SpotifyClientError(Exception):
    """Raised for any Spotify API failure the caller should show to the user."""


class SpotifyClient:
    def __init__(self, client_id, redirect_uri):
        self.auth_manager = SpotifyPKCE(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=SCOPE,
            cache_handler=KeyringCacheHandler(),
            open_browser=True,
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    def is_authenticated(self):
        """True if we have a valid (or refreshable) token, without opening a browser."""
        try:
            token_info = self.auth_manager.cache_handler.get_cached_token()
            if not token_info:
                return False
            if self.auth_manager.is_token_expired(token_info):
                self.auth_manager.refresh_access_token(token_info["refresh_token"])
            return True
        except Exception:
            return False

    def authenticate(self):
        """Runs the interactive PKCE flow (opens the browser). Blocks until complete."""
        try:
            # Newer spotipy releases dropped the `as_dict` kwarg from
            # get_access_token() (it always returns the token string now),
            # so we call it with no arguments for compatibility across
            # spotipy versions.
            self.auth_manager.get_access_token()
        except Exception as e:
            raise SpotifyClientError(f"Spotify authentication failed: {e}")

    def get_current_track(self):
        """
        Returns a dict describing the currently playing track, or None.

        Besides id/uri/name/artists it carries the fields used to recognise
        the *same recording* under a different track ID (isrc, artist_ids,
        duration_ms, match_name) — see _find_playlist_uris for why.
        """
        try:
            playback = self.sp.current_user_playing_track()
        except Exception as e:
            raise SpotifyClientError(f"Could not reach Spotify: {e}")

        if not playback or not isinstance(playback.get("item"), dict):
            return None

        return _track_info(playback["item"])

    def get_user_playlists(self):
        """Returns [{'id':..., 'name':...}, ...] for all playlists the user can modify."""
        try:
            playlists = []
            results = self.sp.current_user_playlists(limit=50)
            while results:
                playlists.extend(results["items"])
                results = self.sp.next(results) if results.get("next") else None
            return [{"id": p["id"], "name": p["name"]} for p in playlists]
        except Exception as e:
            raise SpotifyClientError(f"Could not load playlists: {e}")

    def add_track_to_playlist(self, playlist_id, track_uri):
        try:
            # Call the post-February-2026 endpoint directly (/items, not the
            # retired /tracks) so this works regardless of spotipy version.
            self.sp._post(f"playlists/{playlist_id}/items", payload={"uris": [track_uri]})
        except Exception as e:
            raise SpotifyClientError(f"Could not add track: {e}")

    def remove_track_from_playlist(self, playlist_id, track):
        """
        Removes the currently playing track (a dict from get_current_track)
        from playlist_id, including when the playlist stores it under an
        older track ID.

        Returns True if something was removed, False if the track wasn't in
        the playlist at all.
        """
        try:
            uris = self._find_playlist_uris(playlist_id, track)
            if not uris:
                return False
            # DELETE /playlists/{id}/tracks was removed in Spotify's February
            # 2026 API update; the replacement is /items with an "items" body.
            # We delete the URIs *as stored in the playlist*, which for older
            # additions may differ from the URI that's playing now.
            for i in range(0, len(uris), 100):
                self.sp._delete(
                    f"playlists/{playlist_id}/items",
                    payload={"items": [{"uri": u} for u in uris[i:i + 100]]},
                )
            return True
        except SpotifyClientError:
            raise
        except spotipy.SpotifyException as e:
            raise SpotifyClientError(
                f"Spotify rejected the remove request (HTTP {e.http_status}): {e.msg}"
            )
        except Exception as e:
            raise SpotifyClientError(f"Could not remove track: {e}")

    def _find_playlist_uris(self, playlist_id, track):
        """
        Returns the playlist's own URIs for entries that are the given track.

        Why not just compare URIs: Spotify regularly re-issues the same
        recording under a new track ID (remasters, label moves, album
        re-releases). A song added to a playlist years ago keeps its old ID,
        while the player — and so "currently playing" — reports the new one.
        Spotify used to link the two via a `linked_from` field, but the
        February 2026 API update removed it. So we match in tiers:

          1. exact URI match;
          2. same ISRC (the industry ID of the recording itself);
          3. same normalised title + a shared artist + length within 3s.

        The first tier that finds anything wins, so an exact match never
        drags in other versions of the song that are also in the playlist.
        """
        exact, same_isrc, similar = [], [], []

        results = self.sp._get(f"playlists/{playlist_id}/items", limit=100)
        while results:
            for entry in results.get("items", []):
                # Spotify's February 2026 update moved the track object from
                # entry["track"] to entry["item"]; "track" may now be missing
                # or just a boolean. Accept either shape, but only a dict.
                item = entry.get("item")
                if not isinstance(item, dict):
                    item = entry.get("track")
                if not isinstance(item, dict) or not item.get("uri"):
                    continue
                if item.get("is_local"):
                    continue  # local files can't be matched or removed via the API

                other = _track_info(item)
                if other["uri"] == track["uri"]:
                    exact.append(other["uri"])
                elif track.get("isrc") and other["isrc"] == track["isrc"]:
                    same_isrc.append(other["uri"])
                elif _looks_like_same_song(track, other):
                    similar.append(other["uri"])
            results = self.sp.next(results) if results.get("next") else None

        for tier in (exact, same_isrc, similar):
            if tier:
                return list(dict.fromkeys(tier))  # de-duplicate, keep order
        return []


_VERSION_SUFFIX = re.compile(r"\s+-\s+.*$")        # "Song - Remastered 2011"
_BRACKETED = re.compile(r"[\(\[].*?[\)\]]")         # "Song (2019 Remaster)"
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def _normalise_title(name):
    name = (name or "").lower()
    name = _VERSION_SUFFIX.sub("", name)
    name = _BRACKETED.sub("", name)
    return _NON_ALNUM.sub("", name)


def _track_info(item):
    artists = item.get("artists") or []
    return {
        "id": item.get("id"),
        "uri": item.get("uri"),
        "name": item.get("name"),
        "artists": ", ".join(a.get("name", "") for a in artists),
        "artist_ids": {a.get("id") for a in artists if a.get("id")},
        "artist_names": {(a.get("name") or "").lower() for a in artists if a.get("name")},
        "isrc": ((item.get("external_ids") or {}).get("isrc") or "").upper() or None,
        "duration_ms": item.get("duration_ms"),
        "match_name": _normalise_title(item.get("name")),
    }


def _looks_like_same_song(a, b):
    if not a.get("match_name") or a["match_name"] != b.get("match_name"):
        return False
    if not (a["artist_ids"] & b["artist_ids"] or a["artist_names"] & b["artist_names"]):
        return False
    da, db = a.get("duration_ms"), b.get("duration_ms")
    return da is not None and db is not None and abs(da - db) <= 3000
