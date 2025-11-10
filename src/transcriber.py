import numpy as np
import threading
import time
from faster_whisper import WhisperModel
from typing import Optional


class Transcriber:
    def __init__(
        self,
        model_size: str = "turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        keep_model_loaded: bool = False,
        unload_after_seconds: int = 1800
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None
        self.keep_model_loaded = keep_model_loaded
        self.unload_after_seconds = unload_after_seconds
        self.last_used_time = None
        self.unload_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()

    def load_model(self):
        with self.lock:
            if self.model is None:
                print(f"Loading Whisper model '{self.model_size}' on {self.device}...")
                try:
                    self.model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type
                    )
                    print("Model loaded successfully!")
                except Exception as e:
                    if self.device == "cuda":
                        print(f"Failed to load model on CUDA: {e}")
                        print("Falling back to CPU...")
                        self.device = "cpu"
                        self.compute_type = "int8"
                        self.model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type
                        )
                        print("Model loaded successfully on CPU!")
                    else:
                        raise

    def transcribe(self, audio_data: np.ndarray, language: Optional[str] = None) -> str:
        if self.model is None:
            self.load_model()

        self.last_used_time = time.time()
        self._cancel_unload_timer()

        segments, info = self.model.transcribe(
            audio_data,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        if not self.keep_model_loaded:
            self._schedule_unload()

        return " ".join(text_parts).strip()

    def unload_model(self):
        with self.lock:
            if self.model is not None:
                print("Unloading Whisper model from memory...")
                self.model = None
                print("Model unloaded!")

    def _schedule_unload(self):
        self._cancel_unload_timer()
        self.unload_timer = threading.Timer(self.unload_after_seconds, self._auto_unload)
        self.unload_timer.daemon = True
        self.unload_timer.start()

    def _cancel_unload_timer(self):
        if self.unload_timer is not None:
            self.unload_timer.cancel()
            self.unload_timer = None

    def _auto_unload(self):
        if not self.keep_model_loaded:
            self.unload_model()

    def shutdown(self):
        self._cancel_unload_timer()
        self.unload_model()
