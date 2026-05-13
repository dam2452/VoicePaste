import threading
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
        self._active_lock = threading.Lock()
        self._is_active = False
        self._stop_event = threading.Event()

    def toggle(self) -> None:
        if self._tts.is_speaking or self._is_active:
            self._stop_event.set()
            self._tts.stop()
            log.tts("Stopped")
            self._notifier.update_status("idle")
            return

        with self._active_lock:
            if self._is_active:
                return
            self._is_active = True
            self._stop_event.clear()

        try:
            self._run()
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"TTS error: {e}")
            self._notifier.update_status("idle")
        finally:
            with self._active_lock:
                self._is_active = False

    def _run(self) -> None:
        original = self._clipboard.read_text()
        if not original:
            log.warn("Clipboard is empty")
            return
        text = self._prepare_text(original)
        if text is None or self._stop_event.is_set():
            return
        log.tts(f"Speaking {len(text)} chars...")
        self._notifier.update_status("speaking")
        self._play(text, cache_key=original)
        self._notifier.update_status("idle")

    def _play(self, text: str, cache_key: Optional[str] = None) -> None:
        key = cache_key if cache_key is not None else text

        if self._audio_cache is None:
            self._tts.speak(text)
            return

        cached = self._audio_cache.get(key)
        if cached is not None:
            log.tts("Playing from cache")
            self._tts.play_file(str(cached))
            return

        log.tts("Generating audio...")
        audio_bytes, ext = self._tts.generate(text)

        if self._stop_event.is_set():
            log.tts("Generation cancelled")
            return

        cached_path = self._audio_cache.put(key, audio_bytes, ext)
        self._tts.play_file(str(cached_path))

    def _prepare_text(self, original: str) -> Optional[str]:
        if not (self._pre_summarize and self._tts_system_prompt):
            return original

        log.tts(f"Summarizing for TTS ({len(original)} chars)...")
        self._notifier.update_status("processing")
        summarized = self._summarizer.summarize(original, self._tts_system_prompt)
        if not summarized:
            log.warn("TTS summarization returned nothing")
            self._notifier.update_status("idle")
            return None
        return summarized
