"""
Global hotkey registration with "held-key" protection (PRD section 7).

The `keyboard` library (and Windows key-repeat in general) will re-fire a
hotkey callback repeatedly while the combo is held down. We prevent that by
tracking which shortcuts are "currently down" and refusing to fire again
until a background watcher confirms every key in the combo has been
released.
"""

import threading
import time

import keyboard


class HotkeyManager:
    def __init__(self):
        self._handlers = []
        self._pressed = set()
        self._lock = threading.Lock()

    def clear(self):
        """Unregisters all currently-registered hotkeys."""
        for handler in self._handlers:
            try:
                keyboard.remove_hotkey(handler)
            except (KeyError, ValueError):
                pass
        self._handlers = []
        self._pressed.clear()

    def register(self, shortcut, callback):
        """
        Registers `shortcut` (e.g. "ctrl+alt+1") to fire `callback` exactly
        once per press-and-release, even if held down.
        """
        keys = [k.strip() for k in shortcut.split("+") if k.strip()]

        def on_trigger():
            with self._lock:
                if shortcut in self._pressed:
                    return  # already down; ignore repeats while held
                self._pressed.add(shortcut)
            try:
                callback()
            finally:
                threading.Thread(
                    target=self._wait_for_release, args=(shortcut, keys), daemon=True
                ).start()

        handler = keyboard.add_hotkey(shortcut, on_trigger, suppress=False)
        self._handlers.append(handler)

    def _wait_for_release(self, shortcut, keys):
        # Poll until every key in the combo is no longer physically held.
        while True:
            try:
                if not all(keyboard.is_pressed(k) for k in keys):
                    break
            except Exception:
                break
            time.sleep(0.05)
        with self._lock:
            self._pressed.discard(shortcut)


def is_valid_shortcut(shortcut):
    """Best-effort validation that `keyboard` can parse this combo string."""
    if not shortcut:
        return False
    try:
        keyboard.parse_hotkey(shortcut)
        return True
    except ValueError:
        return False
