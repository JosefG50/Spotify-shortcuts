# Spotify Quick Playlist Manager

A Windows 11 background utility that lets you add/remove the **currently
playing** Spotify track to a configured playlist with a single global
keyboard shortcut.

## How track identification works

Spotify's Web API has no way to see what your mouse is hovering over inside
the Spotify desktop app. The reliable signal it *does* expose is "what's
currently playing." So the workflow this app supports is:

```
Play a track in Spotify -> press your shortcut -> it's added/removed
```

This is more reliable than scraping Spotify's window with Windows UI
Automation, which breaks every time Spotify updates its interface.

## 1. Create a Spotify Developer app

1. Go to https://developer.spotify.com/dashboard and log in.
2. Click **Create app**.
3. Give it any name/description.
4. Under **Redirect URIs**, add exactly:
   ```
   http://127.0.0.1:8888/callback
   ```
5. Save. Copy the **Client ID** shown on the app page — you'll paste this
   into the app's settings window. You do **not** need the Client Secret
   (this app uses the PKCE flow, which doesn't require one).

## 2. Install dependencies

Requires Python 3.10+ on Windows 11.

```powershell
cd spotify_quick_playlist_manager
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> **Note on the `keyboard` library:** on Windows it generally needs to run
> with the same or higher privilege level as the window you want shortcuts
> to work over. If shortcuts don't respond while Spotify is focused, try
> running your terminal (or the packaged .exe) **as Administrator**.

## 3. Run it

```powershell
python main.py
```

On first run (no Client ID saved yet), the settings window opens
automatically:

1. Paste your **Client ID**.
2. Leave the Redirect URI as `http://127.0.0.1:8888/callback` (unless you
   used a different one in step 1).
3. Click **Authenticate with Spotify** — a browser window opens for you to
   approve access, then closes automatically.
4. For each of the 3 slots, pick a playlist from the dropdown and set an
   add/remove shortcut (defaults: `ctrl+alt+1/2/3` to add, `ctrl+shift+1/2/3`
   to remove).
5. Click **Save**.

The window closes and the app keeps running from the system tray (look for
the green icon). Right-click it for **Open Configuration** or **Exit**.

## 4. Use it

1. Play a song in Spotify.
2. Press a configured **add** shortcut → the song is added to that
   playlist; a toast notification confirms it.
3. Press the matching **remove** shortcut → every copy of that song is
   removed from the playlist.
4. Holding a shortcut down does **not** repeat the action — it fires once
   per press.

## Project layout

```
spotify_quick_playlist_manager/
├── main.py             # Entry point: wires everything together, tray + hotkey loop
├── config.py           # Load/save local JSON config, shortcut-conflict detection
├── auth.py             # Secure token cache (Windows Credential Manager via keyring)
├── spotify_client.py   # Spotify Web API calls: current track, add, remove-one-occurrence
├── hotkeys.py          # Global hotkey registration with held-key de-duplication
├── gui.py              # Tkinter settings window
├── tray.py             # System tray icon/menu
├── requirements.txt
└── README.md
```

## Where things are stored

- **Non-sensitive config** (playlist IDs/names, shortcuts, Client ID):
  `%APPDATA%\SpotifyQuickPlaylistManager\config.json`
- **Spotify auth tokens**: Windows Credential Manager (via `keyring`), not
  written to disk in plaintext.

## Known limitations (matches PRD's stated MVP scope)

- Only tracks the **currently playing** song, not arbitrary hovered rows in
  a playlist view — this is the trade-off that makes track identification
  reliable without fragile UI automation.
- Windows 11 only.
- No tray-icon "currently detected track" preview; feedback is via toast
  notification after each action.
- No packaged `.exe` yet — this is run via `python main.py`. If you want a
  standalone executable, `pyinstaller --onefile --noconsole main.py` from
  inside the project folder is a reasonable next step (test the resulting
  `.exe` carefully since `keyboard` and `pystray` sometimes need extra
  PyInstaller hooks).
