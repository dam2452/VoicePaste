import threading
from pynput import keyboard
from typing import Callable


class HotkeyHandler:
    def __init__(
        self,
        voice_callback: Callable,
        youtube_callback: Callable = None,
        file_callback: Callable = None
    ):
        self.voice_callback = voice_callback
        self.youtube_callback = youtube_callback
        self.file_callback = file_callback
        self.is_recording = False
        self.listener = None
        self.current_keys = set()
        self.voice_hotkey_triggered = False
        self.youtube_hotkey_triggered = False
        self.file_hotkey_triggered = False

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
        # noinspection PyBroadException
        try:
            self.current_keys.add(key)

            if self._is_voice_hotkey_pressed() and not self.voice_hotkey_triggered:
                self.voice_hotkey_triggered = True
                self.is_recording = not self.is_recording
                threading.Thread(target=self.voice_callback, args=(self.is_recording,), daemon=True).start()

            if self._is_youtube_hotkey_pressed() and not self.youtube_hotkey_triggered:
                self.youtube_hotkey_triggered = True
                if self.youtube_callback:
                    threading.Thread(target=self.youtube_callback, daemon=True).start()

            if self._is_file_hotkey_pressed() and not self.file_hotkey_triggered:
                self.file_hotkey_triggered = True
                if self.file_callback:
                    threading.Thread(target=self.file_callback, daemon=True).start()
        except Exception:
            pass

    def _on_release(self, key):
        # noinspection PyBroadException
        try:
            if key in self.current_keys:
                self.current_keys.remove(key)
            if not self._is_voice_hotkey_pressed():
                self.voice_hotkey_triggered = False
            if not self._is_youtube_hotkey_pressed():
                self.youtube_hotkey_triggered = False
            if not self._is_file_hotkey_pressed():
                self.file_hotkey_triggered = False
        except Exception:
            pass

    def _is_voice_hotkey_pressed(self):
        has_shift = any(
            k == keyboard.Key.shift or k == keyboard.Key.shift_r
            for k in self.current_keys
        )
        has_v = any(
            hasattr(k, 'char') and k.char and k.char.lower() == 'v'
            for k in self.current_keys
        )
        return has_shift and has_v

    def _is_youtube_hotkey_pressed(self):
        has_shift = any(
            k == keyboard.Key.shift or k == keyboard.Key.shift_r
            for k in self.current_keys
        )
        has_y = any(
            hasattr(k, 'char') and k.char and k.char.lower() == 'y'
            for k in self.current_keys
        )
        return has_shift and has_y

    def _is_file_hotkey_pressed(self):
        has_shift = any(
            k == keyboard.Key.shift or k == keyboard.Key.shift_r
            for k in self.current_keys
        )
        has_f = any(
            hasattr(k, 'char') and k.char and k.char.lower() == 'f'
            for k in self.current_keys
        )
        return has_shift and has_f
