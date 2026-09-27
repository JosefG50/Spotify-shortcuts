"""
System tray icon (PRD section 10 — background/tray operation).
"""

import pystray
from PIL import Image, ImageDraw


def make_icon_image():
    """A simple generated Spotify-green tray icon (no external image file needed)."""
    img = Image.new("RGB", (64, 64), "#191414")
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill="#1DB954")
    d.ellipse((18, 18, 46, 46), fill="#191414")
    return img


def build_tray_icon(on_open_config, on_quit):
    menu = pystray.Menu(
        pystray.MenuItem("Open Configuration", on_open_config),
        pystray.MenuItem("Exit", on_quit),
    )
    return pystray.Icon(
        "spotify_quick_playlist_manager",
        make_icon_image(),
        "Spotify Quick Playlist Manager",
        menu,
    )
