"""
Configuration persistence for Spotify Quick Playlist Manager.

Stores non-sensitive configuration (playlist slots, shortcuts, app credentials)
as local JSON under %APPDATA%. Sensitive Spotify tokens are NOT stored here —
see auth.py, which stores them via the Windows Credential Manager (keyring).
"""

import json
import os

CONFIG_DIR = os.path.join(
    os.getenv("APPDATA", os.path.expanduser("~")), "SpotifyQuickPlaylistManager"
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "client_id": "",
    "redirect_uri": "http://127.0.0.1:8888/callback",
    "slots": [
        {
            "playlist_id": "",
            "playlist_name": "",
            "add_shortcut": "ctrl+alt+1",
            "remove_shortcut": "ctrl+shift+1",
        },
        {
            "playlist_id": "",
            "playlist_name": "",
            "add_shortcut": "ctrl+alt+2",
            "remove_shortcut": "ctrl+shift+2",
        },
        {
            "playlist_id": "",
            "playlist_name": "",
            "add_shortcut": "ctrl+alt+3",
            "remove_shortcut": "ctrl+shift+3",
        },
    ],
}


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    """Load config from disk, creating a default config file on first run."""
    ensure_config_dir()
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def find_shortcut_conflicts(slots):
    """
    Return a list of (first_location, second_location, shortcut) tuples where
    first_location / second_location are (slot_index, 'add_shortcut'|'remove_shortcut').
    Empty shortcuts are ignored.
    """
    seen = {}
    conflicts = []
    for i, slot in enumerate(slots):
        for key in ("add_shortcut", "remove_shortcut"):
            val = (slot.get(key) or "").strip().lower()
            if not val:
                continue
            if val in seen:
                conflicts.append((seen[val], (i, key), val))
            else:
                seen[val] = (i, key)
    return conflicts
