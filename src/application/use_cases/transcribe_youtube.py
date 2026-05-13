import time

from src.core.dtos import CacheEntry
from src.core.interfaces import ICacheManager, IAppNotifier, IClipboard, ITranscriber, IYouTubeDownloader
from src import log


class TranscribeYouTubeUseCase:
    def __init__(
        self,
        clipboard: IClipboard,
        downloader: IYouTubeDownloader,
        transcriber: ITranscriber,
        cache: ICacheManager,
        notifier: IAppNotifier,
    ) -> None:
        self._clipboard = clipboard
        self._downloader = downloader
        self._transcriber = transcriber
        self._cache = cache
        self._notifier = notifier

    def execute(self) -> None:
        # pylint: disable=too-many-try-statements
        try:
            url = self._clipboard.read_text().strip()
            if not url:
                log.warn("Clipboard is empty")
                return

            if not self._downloader.is_valid_url(url):
                log.warn(f"Not a YouTube URL: [dim]{url[:80]}[/dim]")
                return

            cached = self._cache.get(url)
            if cached:
                self._clipboard.write_text(cached.text)
                log.clip("Cached transcription copied to clipboard")
                return

            log.info(f"YouTube: [dim]{url}[/dim]")
            self._notifier.update_status("downloading")

            audio = self._downloader.download_audio(url)
            if not audio:
                log.error("Audio download failed")
                self._notifier.update_status("idle")
                return

            log.info(f"Transcribing: [italic]{audio.source_name}[/italic]")
            self._notifier.update_status("processing")

            text = self._transcriber.transcribe(audio)
            if text:
                log.xscr(text)
                self._clipboard.write_text(text)
                log.clip(f"Copied to clipboard ({len(text)} chars)")
                self._cache.put(url, CacheEntry(
                    text=text, timestamp=time.time(),
                    source_type='youtube', title=audio.source_name,
                ))
            else:
                log.warn("No transcription result")

            self._notifier.update_status("idle")

        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"YouTube transcription error: {e}")
            self._notifier.update_status("idle")
