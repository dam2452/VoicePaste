from pathlib import Path
import sys
from typing import List

import pyperclip


class OsClipboard:
    @staticmethod
    def read_text() -> str:
        try:
            return pyperclip.paste()
        except Exception:  # pylint: disable=broad-exception-caught
            return ""

    @staticmethod
    def write_text(text: str) -> None:
        try:
            pyperclip.copy(text)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    @staticmethod
    def read_file_paths() -> List[str]:
        file_paths = []

        if sys.platform == 'win32':
            # pylint: disable=import-outside-toplevel,c-extension-no-member
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                        files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                        if files:
                            file_paths = [f for f in files if Path(f).is_file()]
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            # pylint: enable=import-outside-toplevel,c-extension-no-member
        elif sys.platform == 'darwin':
            # pylint: disable=import-outside-toplevel
            try:
                from AppKit import NSFilenamesPboardType, NSPasteboard
                pasteboard = NSPasteboard.generalPasteboard()
                if NSFilenamesPboardType in pasteboard.types():
                    files = pasteboard.propertyListForType_(NSFilenamesPboardType)
                    if files:
                        file_paths = [f for f in files if Path(f).is_file()]
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if not file_paths:
            text = OsClipboard.read_text()
            if text:
                file_paths = [
                    cleaned for line in text.strip().split('\n')
                    if Path(cleaned := line.strip().strip('"').strip("'")).is_file()
                ]

        return file_paths
