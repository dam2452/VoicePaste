import numpy as np
import threading
import time
import gc
from faster_whisper import WhisperModel
from typing import Optional


class Transcriber:
    def __init__(
        self,
        model_size: str = "turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        keep_model_loaded: bool = False,
        move_to_ram_after_seconds: int = 3600,
        unload_after_seconds: int = 18000
    ):
        self.model_size = model_size
        self.preferred_device = device
        self.gpu_compute_type = compute_type
        self.cpu_compute_type = "int8"
        self.model: Optional[WhisperModel] = None
        self.current_device: Optional[str] = None
        self.keep_model_loaded = keep_model_loaded
        self.move_to_ram_after_seconds = move_to_ram_after_seconds
        self.unload_after_seconds = unload_after_seconds
        self.last_used_time = None
        self.ram_timer: Optional[threading.Timer] = None
        self.disk_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.preload_thread: Optional[threading.Thread] = None
        self.is_preloading = False

    def load_model(self, target_device: Optional[str] = None):
        with self.lock:
            if self.model is None:
                device = target_device or self.preferred_device
                compute_type = self.gpu_compute_type if device == "cuda" else self.cpu_compute_type

                print(f"Loading Whisper model '{self.model_size}' on {device}...")
                try:
                    self.model = WhisperModel(
                        self.model_size,
                        device=device,
                        compute_type=compute_type
                    )
                    self.current_device = device
                    print(f"Model loaded successfully on {device.upper()}!")
                except Exception as e:
                    if device == "cuda":
                        print(f"Failed to load model on CUDA: {e}")
                        print("Falling back to CPU...")
                        self.model = WhisperModel(
                            self.model_size,
                            device="cpu",
                            compute_type=self.cpu_compute_type
                        )
                        self.current_device = "cpu"
                        self.preferred_device = "cpu"
                        print("Model loaded successfully on CPU!")
                    else:
                        raise

    def transcribe(self, audio_data: np.ndarray, language: Optional[str] = None) -> str:
        if self.is_preloading and self.preload_thread is not None:
            print("Waiting for model preload to complete...")
            self.preload_thread.join()
            self.is_preloading = False

        if self.model is None:
            self.load_model()
        elif self.current_device == "cpu" and self.preferred_device == "cuda":
            print("Model on CPU, moving back to GPU for transcription...")
            self._move_to_gpu()

        self.last_used_time = time.time()
        self._cancel_all_timers()

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
            self._schedule_memory_management()

        return " ".join(text_parts).strip()

    def unload_model(self):
        with self.lock:
            if self.model is not None:
                print("Unloading Whisper model from memory (moving to disk)...")
                self.model = None
                self.current_device = None
                gc.collect()
                print("Model unloaded!")

    def _move_to_cpu(self):
        with self.lock:
            if self.model is not None and self.current_device == "cuda":
                print("Moving model from VRAM to RAM (GPU -> CPU)...")
                self.model = None
                gc.collect()

                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type=self.cpu_compute_type
                )
                self.current_device = "cpu"
                print("Model moved to RAM (CPU)!")

    def _move_to_gpu(self):
        with self.lock:
            if self.model is not None and self.current_device == "cpu" and self.preferred_device == "cuda":
                print("Moving model from RAM to VRAM (CPU -> GPU)...")
                self.model = None
                gc.collect()

                try:
                    self.model = WhisperModel(
                        self.model_size,
                        device="cuda",
                        compute_type=self.gpu_compute_type
                    )
                    self.current_device = "cuda"
                    print("Model moved to VRAM (GPU)!")
                except Exception as e:
                    print(f"Failed to move to GPU: {e}, keeping on CPU")
                    self.model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type=self.cpu_compute_type
                    )
                    self.current_device = "cpu"

    def _schedule_memory_management(self):
        self._cancel_all_timers()

        if self.current_device == "cuda":
            self.ram_timer = threading.Timer(self.move_to_ram_after_seconds, self._auto_move_to_ram)
            self.ram_timer.daemon = True
            self.ram_timer.start()
        elif self.current_device == "cpu":
            self.disk_timer = threading.Timer(self.unload_after_seconds, self._auto_unload)
            self.disk_timer.daemon = True
            self.disk_timer.start()

    def _cancel_all_timers(self):
        if self.ram_timer is not None:
            self.ram_timer.cancel()
            self.ram_timer = None
        if self.disk_timer is not None:
            self.disk_timer.cancel()
            self.disk_timer = None

    def _auto_move_to_ram(self):
        if not self.keep_model_loaded:
            self._move_to_cpu()
            self.disk_timer = threading.Timer(self.unload_after_seconds, self._auto_unload)
            self.disk_timer.daemon = True
            self.disk_timer.start()

    def _auto_unload(self):
        if not self.keep_model_loaded:
            self.unload_model()

    def preload_for_recording(self):
        if self.is_preloading:
            return

        if self.model is None:
            print("Preloading model to VRAM during recording...")
            self.is_preloading = True
            self.preload_thread = threading.Thread(target=self._preload_worker, daemon=True)
            self.preload_thread.start()
        elif self.current_device == "cpu" and self.preferred_device == "cuda":
            print("Preloading model to VRAM during recording...")
            self.is_preloading = True
            self.preload_thread = threading.Thread(target=self._move_to_gpu, daemon=True)
            self.preload_thread.start()

    def _preload_worker(self):
        try:
            self.load_model()
        finally:
            self.is_preloading = False

    def shutdown(self):
        self._cancel_all_timers()
        if self.preload_thread is not None and self.preload_thread.is_alive():
            self.preload_thread.join(timeout=5)
        self.unload_model()
