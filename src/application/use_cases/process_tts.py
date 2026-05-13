from typing import Optional

from src.application.services.tts_audio_cache import TTSAudioCache
from src.core.interfaces import IAppNotifier, IClipboard, ISummarizer, ITTSEngine
from src import log


class ProcessTTSUseCase:
    def __init__(
        self,
        clipboard: IClipboard,
        tts: ITTSEngine,
        notifier: IAppNotifier,
        summarizer: ISummarizer,
        tts_system_prompt: str = "",
        pre_summarize: bool = False,
        audio_cache: Optional[TTSAudioCache] = None,
    ) -> None:
        self._clipboard = clipboard
        self._tts = tts
        self._notifier = notifier
        self._summarizer = summarizer
        self._tts_system_prompt = tts_system_prompt
        self._pre_summarize = pre_summarize
        self._audio_cache = audio_cache

    def toggle(self) -> None:
        if self._tts.is_speaking:
            self._tts.stop()
            log.tts("Stopped")
            self._notifier.update_status("idle")
            return

        try:
            text = self._prepare_text()
            if text is None:
                return
            log.tts(f"Speaking {len(text)} chars...")
            self._notifier.update_status("speaking")
            self._play(text)
            self._notifier.update_status("idle")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"TTS error: {e}")
            self._notifier.update_status("idle")

    def _play(self, text: str) -> None:
        if self._audio_cache is None:
            self._tts.speak(text)
            return

        cached = self._audio_cache.get(text)
        if cached is not None:
            self._tts.play_file(str(cached))
            return

        audio_bytes, ext = self._tts.generate(text)
        cached_path = self._audio_cache.put(text, audio_bytes, ext)
        self._tts.play_file(str(cached_path))

    def _prepare_text(self) -> Optional[str]:
        text = self._clipboard.read_text()
        if not text:
            log.warn("Clipboard is empty")
            return None

        if not (self._pre_summarize and self._tts_system_prompt):
            return text

        log.tts(f"Summarizing for TTS ({len(text)} chars)...")
        self._notifier.update_status("processing")
        summarized = self._summarizer.summarize(text, self._tts_system_prompt)
        if not summarized:
            log.warn("TTS summarization returned nothing")
            self._notifier.update_status("idle")
            return None
        return summarized
