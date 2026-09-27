"""
Small configuration GUI (PRD sections 8-9). Deliberately minimal: credentials,
three playlist slots (playlist / add shortcut / remove shortcut), and a Save
button. The app does not need this window open to function (section 10).
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox

import config as cfg
from hotkeys import is_valid_shortcut
from spotify_client import SpotifyClient, SpotifyClientError

NO_PLAYLIST = "(select a playlist)"


def _deep_copy(d):
    return json.loads(json.dumps(d))


class ConfigWindow(tk.Toplevel):
    def __init__(self, master, config, spotify_client, on_save):
        super().__init__(master)
        self.title("Spotify Quick Playlist Manager - Settings")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.config_data = _deep_copy(config)
        self.spotify = spotify_client
        self.on_save = on_save
        self.playlists = []
        self.playlist_names = [NO_PLAYLIST]

        self._build_auth_section()
        self._build_slot_sections()
        self._build_save_section()

        if self.spotify and self._safe_is_authenticated():
            self.auth_status_var.set("Authenticated \u2713")
            self._load_playlists()

    # -- helpers ---------------------------------------------------------

    def _safe_is_authenticated(self):
        try:
            return self.spotify.is_authenticated()
        except Exception:
            return False

    # -- sections ----------------------------------------------------------

    def _build_auth_section(self):
        frame = ttk.LabelFrame(self, text="Spotify App Credentials")
        frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ttk.Label(frame, text="Client ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.client_id_var = tk.StringVar(value=self.config_data.get("client_id", ""))
        ttk.Entry(frame, textvariable=self.client_id_var, width=42).grid(
            row=0, column=1, padx=5, pady=5
        )

        ttk.Label(frame, text="Redirect URI:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.redirect_uri_var = tk.StringVar(
            value=self.config_data.get("redirect_uri", "http://127.0.0.1:8888/callback")
        )
        ttk.Entry(frame, textvariable=self.redirect_uri_var, width=42).grid(
            row=1, column=1, padx=5, pady=5
        )

        self.auth_status_var = tk.StringVar(value="Not authenticated")
        ttk.Label(frame, textvariable=self.auth_status_var, foreground="#1DB954").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=5
        )

        ttk.Button(
            frame, text="Authenticate with Spotify", command=self._authenticate
        ).grid(row=3, column=0, columnspan=2, pady=8)

    def _authenticate(self):
        client_id = self.client_id_var.get().strip()
        redirect_uri = self.redirect_uri_var.get().strip()
        if not client_id:
            messagebox.showerror("Missing Client ID", "Enter your Spotify app's Client ID first.")
            return
        try:
            self.spotify = SpotifyClient(client_id, redirect_uri)
            self.spotify.authenticate()  # opens browser, blocks until redirect captured
            self.auth_status_var.set("Authenticated \u2713")
            self._load_playlists()
        except SpotifyClientError as e:
            messagebox.showerror("Authentication failed", str(e))

    def _load_playlists(self):
        try:
            self.playlists = self.spotify.get_user_playlists()
        except SpotifyClientError as e:
            messagebox.showerror("Could not load playlists", str(e))
            return
        self.playlist_names = [NO_PLAYLIST] + [p["name"] for p in self.playlists]
        for combo in self.slot_combos:
            combo["values"] = self.playlist_names
        self._select_current_playlists()

    def _select_current_playlists(self):
        for i, slot in enumerate(self.config_data["slots"]):
            pid = slot.get("playlist_id")
            if pid:
                match = next((p["name"] for p in self.playlists if p["id"] == pid), None)
                if match:
                    self.slot_vars[i]["playlist"].set(match)

    def _build_slot_sections(self):
        self.slot_vars = []
        self.slot_combos = []
        slots = self.config_data.get("slots", [])
        for i, slot in enumerate(slots):
            frame = ttk.LabelFrame(self, text=f"Playlist Slot {i + 1}")
            frame.grid(row=i + 1, column=0, padx=10, pady=5, sticky="ew")

            ttk.Label(frame, text="Playlist:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
            playlist_var = tk.StringVar(value=slot.get("playlist_name") or NO_PLAYLIST)
            combo = ttk.Combobox(
                frame,
                textvariable=playlist_var,
                values=self.playlist_names,
                width=32,
                state="readonly",
            )
            combo.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w")
            self.slot_combos.append(combo)

            ttk.Label(frame, text="Add shortcut:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            add_var = tk.StringVar(value=slot.get("add_shortcut", ""))
            ttk.Entry(frame, textvariable=add_var, width=20).grid(
                row=1, column=1, padx=5, pady=5, sticky="w"
            )

            ttk.Label(frame, text="Remove shortcut:").grid(
                row=1, column=2, sticky="w", padx=5, pady=5
            )
            remove_var = tk.StringVar(value=slot.get("remove_shortcut", ""))
            ttk.Entry(frame, textvariable=remove_var, width=20).grid(
                row=1, column=3, padx=5, pady=5, sticky="w"
            )

            self.slot_vars.append({"playlist": playlist_var, "add": add_var, "remove": remove_var})

    def _build_save_section(self):
        ttk.Button(self, text="Save", command=self._save).grid(
            row=len(self.config_data["slots"]) + 1, column=0, pady=12
        )

    # -- save --------------------------------------------------------------

    def _save(self):
        new_slots = []
        for i, vars_ in enumerate(self.slot_vars):
            playlist_name = vars_["playlist"].get()
            playlist_id = ""
            if playlist_name and playlist_name != NO_PLAYLIST:
                match = next((p["id"] for p in self.playlists if p["name"] == playlist_name), None)
                playlist_id = match or self.config_data["slots"][i].get("playlist_id", "")

            add_shortcut = vars_["add"].get().strip().lower()
            remove_shortcut = vars_["remove"].get().strip().lower()

            for shortcut in (add_shortcut, remove_shortcut):
                if shortcut and not is_valid_shortcut(shortcut):
                    messagebox.showerror(
                        "Invalid shortcut",
                        f"'{shortcut}' in Slot {i + 1} is not a valid key combination.\n"
                        "Use the form: ctrl+alt+1",
                    )
                    return

            new_slots.append(
                {
                    "playlist_id": playlist_id,
                    "playlist_name": playlist_name if playlist_name != NO_PLAYLIST else "",
                    "add_shortcut": add_shortcut,
                    "remove_shortcut": remove_shortcut,
                }
            )

        conflicts = cfg.find_shortcut_conflicts(new_slots)
        if conflicts:
            details = "\n".join(
                f"Slot {a[0] + 1} and Slot {b[0] + 1} both use '{val}'" for a, b, val in conflicts
            )
            messagebox.showerror("Shortcut conflict", f"Fix these conflicts before saving:\n\n{details}")
            return

        self.config_data["client_id"] = self.client_id_var.get().strip()
        self.config_data["redirect_uri"] = self.redirect_uri_var.get().strip()
        self.config_data["slots"] = new_slots

        self.on_save(self.config_data, self.spotify)
        self.destroy()
