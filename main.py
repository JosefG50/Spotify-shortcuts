"""
Spotify Quick Playlist Manager - entry point.

Run this file to start the background application. It will:
  1. Load (or create) local configuration.
  2. Register global hotkeys for each configured playlist slot.
  3. Show a system tray icon (Open Configuration / Exit).

The configuration window can be reopened at any time from the tray icon;
the app functions fully without it open (PRD section 10).
"""

import queue
import threading
import tkinter as tk

import config as cfg
from gui import ConfigWindow
from hotkeys import HotkeyManager
from spotify_client import SpotifyClient, SpotifyClientError
from tray import build_tray_icon

command_queue = queue.Queue()


class App:
    def __init__(self):
        self.config = cfg.load_config()
        self.root = tk.Tk()
        self.root.withdraw()  # no main window; tray-only UX

        self.spotify = None
        self.hotkeys = HotkeyManager()
        self.config_window = None

        self.icon = build_tray_icon(
            on_open_config=lambda icon, item: command_queue.put("open_gui"),
            on_quit=lambda icon, item: command_queue.put("quit"),
        )

        self._init_spotify()
        self._register_hotkeys()

    # -- setup -------------------------------------------------------------

    def _init_spotify(self):
        if self.config.get("client_id"):
            try:
                self.spotify = SpotifyClient(
                    self.config["client_id"], self.config["redirect_uri"]
                )
            except Exception:
                self.spotify = None

    def _register_hotkeys(self):
        self.hotkeys.clear()

        conflicts = cfg.find_shortcut_conflicts(self.config["slots"])
        if conflicts:
            self.notify(
                "Two or more slots share the same shortcut. Open settings to fix it.",
                "\u26a0 Configuration error",
            )
            return

        for slot in self.config["slots"]:
            if slot.get("playlist_id"):
                if slot.get("add_shortcut"):
                    self.hotkeys.register(slot["add_shortcut"], self._make_handler("add", slot))
                if slot.get("remove_shortcut"):
                    self.hotkeys.register(slot["remove_shortcut"], self._make_handler("remove", slot))

    # -- actions -------------------------------------------------------------

    def _make_handler(self, action, slot):
        def handler():
            self._do_action(action, slot)
        return handler

    def _do_action(self, action, slot):
        if not self.spotify or not self.spotify.is_authenticated():
            self.notify("Open settings and authenticate with Spotify.", "\u26a0 Spotify authentication required")
            return

        try:
            track = self.spotify.get_current_track()
        except SpotifyClientError as e:
            self.notify(str(e), "\u26a0 Spotify unavailable")
            return

        if not track:
            self.notify("Play a track in Spotify first.", "\u26a0 Track not found")
            return

        playlist_name = slot.get("playlist_name") or "playlist"
        try:
            if action == "add":
                self.spotify.add_track_to_playlist(slot["playlist_id"], track["uri"])
                self.notify(f'{track["name"]} \u2014 {track["artists"]}', f'\u2713 Added to {playlist_name}')
            else:
                removed = self.spotify.remove_track_from_playlist(slot["playlist_id"], track)
                if removed:
                    self.notify(f'{track["name"]} \u2014 {track["artists"]}', f'\u2713 Removed from {playlist_name}')
                else:
                    self.notify(f'{track["name"]} isn\'t in {playlist_name}', "Nothing to remove")
        except SpotifyClientError as e:
            self.notify(str(e), "\u26a0 Spotify API error")

    def notify(self, message, title="Spotify Quick Playlist Manager"):
        try:
            self.icon.notify(message, title)
        except Exception:
            print(f"{title}: {message}")

    # -- GUI / lifecycle -----------------------------------------------------

    def open_config(self):
        if self.config_window is not None and self.config_window.winfo_exists():
            self.config_window.deiconify()
            self.config_window.lift()
            return
        self.config_window = ConfigWindow(
            self.root, self.config, self.spotify, on_save=self._on_config_saved
        )

    def _on_config_saved(self, new_config, new_spotify_client):
        self.config = new_config
        cfg.save_config(self.config)
        if new_spotify_client:
            self.spotify = new_spotify_client
        self._register_hotkeys()
        self.notify("Configuration saved.", "Settings updated")

    def poll_queue(self):
        try:
            while True:
                cmd = command_queue.get_nowait()
                if cmd == "open_gui":
                    self.open_config()
                elif cmd == "quit":
                    self.shutdown()
                    return
        except queue.Empty:
            pass
        self.root.after(150, self.poll_queue)

    def shutdown(self):
        self.hotkeys.clear()
        try:
            self.icon.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()

    def run(self):
        threading.Thread(target=self.icon.run, daemon=True).start()
        # First run: no client_id configured yet, so open settings immediately.
        if not self.config.get("client_id"):
            self.root.after(300, self.open_config)
        self.root.after(150, self.poll_queue)
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
