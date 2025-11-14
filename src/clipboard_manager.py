import pyperclip
import sys
from typing import Optional
from pathlib import Path


class ClipboardManager:
    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        # noinspection PyBroadException
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    @staticmethod
    def get_from_clipboard() -> str:
        # noinspection PyBroadException
        try:
            return pyperclip.paste()
        except Exception:
            return ""

    @staticmethod
    def get_file_path_from_clipboard() -> Optional[str]:
        if sys.platform == 'win32':
            # noinspection PyBroadException
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                        files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                        if files and len(files) > 0:
                            file_path = files[0]
                            if Path(file_path).is_file():
                                return file_path
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass
        elif sys.platform == 'darwin':
            # noinspection PyBroadException
            try:
                # noinspection PyPackageRequirements,PyUnresolvedReferences
                from AppKit import NSPasteboard, NSFilenamesPboardType
                pasteboard = NSPasteboard.generalPasteboard()
                if NSFilenamesPboardType in pasteboard.types():
                    files = pasteboard.propertyListForType_(NSFilenamesPboardType)
                    if files and len(files) > 0:
                        file_path = files[0]
                        if Path(file_path).is_file():
                            return file_path
            except Exception:
                pass

        text = ClipboardManager.get_from_clipboard()
        if text:
            text = text.strip().strip('"').strip("'")
            if Path(text).is_file():
                return text

        return None
