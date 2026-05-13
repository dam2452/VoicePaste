import threading
import time

import numpy as np

from src.core.dtos import CacheEntry
from src.core.interfaces import IAudioRecorder, ICacheManager, IAppNotifier, IClipboard, ITranscriber
from src import log


class RecordVoiceUseCase:
    def __init__(
        self,
        recorder: IAudioRecorder,
        transcriber: ITranscriber,
        clipboard: IClipboard,
        cache: ICacheManager,
        notifier: IAppNotifier,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._clipboard = clipboard
        self._cache = cache
        self._notifier = notifier
        self._is_recording = False
        self._lock = threading.Lock()

    def toggle(self) -> None:
        with self._lock:
            if self._is_recording:
                self._is_recording = False
                threading.Thread(target=self._stop_and_process, daemon=True).start()
            else:
                self._is_recording = True
                self._start()

    def _start(self) -> None:
        try:
            log.rec("Recording...")
            self._notifier.update_status("recording")
            self._recorder.start_recording()
            self._transcriber.preload_for_recording()
        except RuntimeError as e:
            log.error(f"Recording start error: {e}")
            with self._lock:
                self._is_recording = False
            self._notifier.update_status("idle")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Unexpected error: {e}")
            with self._lock:
                self._is_recording = False
            self._notifier.update_status("idle")

    def _stop_and_process(self) -> None:
        log.rec("Recording stopped - processing...")
        self._notifier.update_status("processing")

        audio = self._recorder.stop_recording()
        if audio is None:
            log.warn("No audio data captured")
            self._notifier.update_status("idle")
            return

        duration = len(audio.data) / audio.sample_rate

        if len(audio.data) < 1600:
            log.warn(f"Recording too short ({duration:.2f}s) - ignoring")
            self._notifier.update_status("idle")
            return

        rms = np.sqrt(np.mean(audio.data**2))
        log.audio_info(f"{duration:.2f}s / {len(audio.data)} samples / RMS {rms:.4f}")

        try:
            text = self._transcriber.transcribe(audio)
            if text:
                log.xscr(text)
                self._clipboard.write_text(text)
                log.clip(f"Copied to clipboard ({len(text)} chars)")
                self._cache.put(
                    f"voice_{int(time.time() * 1000)}",
                    CacheEntry(
                        text=text,
                        timestamp=time.time(),
                        source_type='voice',
                        title=f"Voice Recording ({duration:.1f}s)",
                    ),
                )
            else:
                log.warn("Whisper returned no text")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Transcription error: {e}")

        self._notifier.update_status("idle")
