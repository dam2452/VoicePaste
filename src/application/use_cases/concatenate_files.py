import threading
from pathlib import Path
from typing import Callable, Optional

from src.core.interfaces import IClipboard
from src import log


class ConcatenateFilesUseCase:
    def __init__(
        self,
        clipboard: IClipboard,
        concat_session: object,
        open_dialog: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self._clipboard = clipboard
        self._concat_session = concat_session
        self._open_dialog = open_dialog

    def execute(self) -> None:
        clipboard_text = self._clipboard.read_text()
        if not clipboard_text:
            log.warn("Clipboard is empty")
            return

        text = clipboard_text.strip().strip('"').strip("'")
        if Path(text).is_dir():
            log.info(f"Folder detected - opening dialog: [dim]{text}[/dim]")
            if self._open_dialog:
                threading.Thread(target=self._open_dialog, args=(text,), daemon=True).start()
            return

        message = self._concat_session.process_clipboard(clipboard_text)
        log.info(message)
