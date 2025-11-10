import threading
from pynput import keyboard
from typing import Callable


class HotkeyHandler:
    def __init__(self, callback: Callable):
        self.callback = callback
        self.is_recording = False
        self.listener = None
        self.current_keys = set()
        self.hotkey_triggered = False

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()

    def _on_press(self, key):
        try:
            self.current_keys.add(key)
            if self._is_hotkey_pressed() and not self.hotkey_triggered:
                self.hotkey_triggered = True
                self.is_recording = not self.is_recording
                threading.Thread(target=self.callback, args=(self.is_recording,), daemon=True).start()
        except Exception:
            pass

    def _on_release(self, key):
        try:
            if key in self.current_keys:
                self.current_keys.remove(key)
            if not self._is_hotkey_pressed():
                self.hotkey_triggered = False
        except Exception:
            pass

    def _is_hotkey_pressed(self):
        has_shift = any(
            k == keyboard.Key.shift or k == keyboard.Key.shift_r
            for k in self.current_keys
        )
        has_v = any(
            hasattr(k, 'char') and k.char and k.char.lower() == 'v'
            for k in self.current_keys
        )
        return has_shift and has_v
