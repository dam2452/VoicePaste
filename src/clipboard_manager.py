import pyperclip


class ClipboardManager:
    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    @staticmethod
    def get_from_clipboard() -> str:
        try:
            return pyperclip.paste()
        except Exception:
            return ""
