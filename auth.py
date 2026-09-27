"""
Secure token storage for the Spotify PKCE auth flow.

Instead of spotipy's default plaintext .cache file, tokens are stored via
`keyring`, which on Windows 11 uses the Windows Credential Manager. This
satisfies the PRD's requirement that sensitive authentication information
must not be stored in plain text unnecessarily (section 13, section 18).
"""

import json
import keyring
from spotipy.cache_handler import CacheHandler

SERVICE_NAME = "SpotifyQuickPlaylistManager"
KEY_NAME = "spotify_token_info"


class KeyringCacheHandler(CacheHandler):
    """Stores/retrieves the Spotify token dict via the OS credential store."""

    def get_cached_token(self):
        try:
            raw = keyring.get_password(SERVICE_NAME, KEY_NAME)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def save_token_to_cache(self, token_info):
        try:
            keyring.set_password(SERVICE_NAME, KEY_NAME, json.dumps(token_info))
        except Exception:
            # If the OS credential store is unavailable, we degrade gracefully:
            # the user will simply be asked to re-authenticate next launch.
            pass

    def clear_cached_token(self):
        try:
            keyring.delete_password(SERVICE_NAME, KEY_NAME)
        except Exception:
            pass
