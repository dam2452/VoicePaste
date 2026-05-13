from src.core.interfaces import IAppNotifier, IClipboard, ISummarizer
from src import log


class SummarizeClipboardUseCase:
    def __init__(
        self,
        clipboard: IClipboard,
        summarizer: ISummarizer,
        notifier: IAppNotifier,
    ) -> None:
        self._clipboard = clipboard
        self._summarizer = summarizer
        self._notifier = notifier

    def execute(self) -> None:
        try:
            text = self._clipboard.read_text()
            if not text:
                log.warn("Clipboard is empty")
                return
            log.info(f"Summarizing {len(text)} chars...")
            self._notifier.update_status("processing")
            self._run_summary(text)
            self._notifier.update_status("idle")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Summarization error: {e}")
            self._notifier.update_status("idle")

    def _run_summary(self, text: str) -> None:
        summary = self._summarizer.summarize(text)
        if summary:
            self._clipboard.write_text(summary)
            log.xscr(summary)
            log.clip(f"Summary copied to clipboard ({len(summary)} chars)")
        else:
            log.warn("No summary returned")
