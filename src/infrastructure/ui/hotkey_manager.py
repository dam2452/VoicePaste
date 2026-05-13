from typing import Callable, Dict, Optional, Set

from pynput import keyboard


class HotkeyManager:
    def __init__(self) -> None:
        self._bindings: Dict[str, Callable[[], None]] = {}
        self._triggered: Set[str] = set()
        self._current_keys: Set = set()
        self._listener: Optional[keyboard.Listener] = None

    def bind_shift(self, key_char: str, callback: Callable[[], None]) -> None:
        self._bindings[key_char.lower()] = callback

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()

    def _on_press(self, key) -> None:
        try:
            self._current_keys.add(key)
            if not self._has_shift():
                return
            char = self._pressed_char()
            if char and char in self._bindings and char not in self._triggered:
                self._triggered.add(char)
                self._bindings[char]()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _on_release(self, key) -> None:
        try:
            self._current_keys.discard(key)
            if not self._has_shift():
                self._triggered.clear()
            else:
                released_char = self._key_char(key)
                if released_char:
                    self._triggered.discard(released_char)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _has_shift(self) -> bool:
        return any(k in (keyboard.Key.shift, keyboard.Key.shift_r) for k in self._current_keys)

    def _pressed_char(self) -> Optional[str]:
        for k in self._current_keys:
            c = self._key_char(k)
            if c:
                return c
        return None

    @staticmethod
    def _key_char(key) -> Optional[str]:
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
        return None
