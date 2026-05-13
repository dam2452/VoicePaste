import gc
import threading
import time
from typing import Optional

from faster_whisper import WhisperModel

from src.core.dtos import AudioData
from src import log


class FasterWhisperTranscriber:
    def __init__(
        self,
        model_size: str = "turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        keep_model_loaded: bool = False,
        move_to_ram_after_seconds: int = 3600,
        unload_after_seconds: int = 18000,
        gpu_profile: str = "standard",
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
        self.gpu_profile = gpu_profile
        self._set_quality_params()

    def _set_quality_params(self) -> None:
        if self.gpu_profile == "high_end":
            self.beam_size = 10
            self.patience = 1.5
        else:
            self.beam_size = 5
            self.patience = 1.0
        self.temperature = 0.0
        self.compression_ratio_threshold = 2.4
        self.log_prob_threshold = -1.0
        self.no_speech_threshold = 0.6

    def set_gpu_profile(self, profile: str) -> None:
        if profile not in ("standard", "high_end"):
            log.error(f"Invalid GPU profile: {profile}. Use 'standard' or 'high_end'")
            return
        self.gpu_profile = profile
        self._set_quality_params()
        if profile == "high_end":
            log.model(f"GPU profile: [bold]high_end[/bold]  beam={self.beam_size} patience={self.patience} (RTX 3090+)")
        else:
            log.model(f"GPU profile: [bold]standard[/bold]  beam={self.beam_size} patience={self.patience} (RTX 2080S)")

    def get_model_status(self) -> str:
        if self.model is None:
            return "Not loaded"
        if self.current_device == "cuda":
            return "VRAM (GPU)"
        if self.current_device == "cpu":
            return "RAM (CPU)"
        return "Unknown"

    def load_model(self, target_device: Optional[str] = None) -> None:
        with self.lock:
            if self.model is not None:
                return
            device = target_device or self.preferred_device
            compute_type = self.gpu_compute_type if device == "cuda" else self.cpu_compute_type
            log.model(f"Loading whisper-{self.model_size} on [bold]{device.upper()}[/bold] ({compute_type})...")
            try:
                self.model = WhisperModel(self.model_size, device=str(device), compute_type=compute_type)
                self.current_device = device
                log.model(f"Model ready on [bold]{device.upper()}[/bold]")
            except Exception as e:  # pylint: disable=broad-exception-caught
                if device == "cuda":
                    log.warn(f"CUDA load failed: {e} - falling back to CPU")
                    self.model = WhisperModel(self.model_size, device="cpu", compute_type=self.cpu_compute_type)
                    self.current_device = "cpu"
                    self.preferred_device = "cpu"
                    log.model("Model ready on [bold]CPU[/bold]")
                else:
                    raise

    def transcribe(self, audio: AudioData, language: Optional[str] = None) -> str:
        if self.is_preloading and self.preload_thread is not None:
            log.model("Waiting for model preload...")
            self.preload_thread.join()
            self.is_preloading = False

        if self.model is None:
            self.load_model()
        elif self.current_device == "cpu" and self.preferred_device == "cuda":
            log.model("Moving model CPU -> GPU for transcription...")
            self._move_to_gpu()

        self.last_used_time = time.time()
        self._cancel_all_timers()

        samples = audio.data
        log.model(f"Transcribing [dim]{len(samples)} samples ({len(samples)/16000:.1f}s)[/dim]...")
        segments, _ = self.model.transcribe(
            samples,
            language=language,
            beam_size=self.beam_size,
            patience=self.patience,
            temperature=self.temperature,
            compression_ratio_threshold=self.compression_ratio_threshold,
            log_prob_threshold=self.log_prob_threshold,
            no_speech_threshold=self.no_speech_threshold,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        text_parts = []
        segment_count = 0
        for seg in segments:
            segment_count += 1
            log.segment(segment_count, seg.text, seg.avg_logprob)
            text_parts.append(seg.text)

        log.model(f"[dim]{segment_count} segment(s) detected[/dim]")

        if not self.keep_model_loaded:
            self._schedule_memory_management()

        return " ".join(text_parts).strip()

    def preload_for_recording(self) -> None:
        if self.is_preloading:
            return
        if self.model is None:
            log.model("Preloading model to VRAM during recording...")
            self.is_preloading = True
            self.preload_thread = threading.Thread(target=self._preload_worker, daemon=True)
            self.preload_thread.start()
        elif self.current_device == "cpu" and self.preferred_device == "cuda":
            log.model("Moving model to VRAM during recording...")
            self.is_preloading = True
            self.preload_thread = threading.Thread(target=self._move_to_gpu, daemon=True)
            self.preload_thread.start()

    def unload_model(self) -> None:
        with self.lock:
            if self.model is not None:
                log.model("Unloading model from memory...")
                self.model = None
                self.current_device = None
                gc.collect()
                log.model("Model unloaded")

    def shutdown(self) -> None:
        self._cancel_all_timers()
        if self.preload_thread is not None and self.preload_thread.is_alive():
            self.preload_thread.join(timeout=5)
        self.unload_model()

    def _move_to_cpu(self) -> None:
        with self.lock:
            if self.model is not None and self.current_device == "cuda":
                log.model("Moving model VRAM -> RAM (GPU -> CPU)...")
                self.model = None
                gc.collect()
                self.model = WhisperModel(self.model_size, device="cpu", compute_type=self.cpu_compute_type)
                self.current_device = "cpu"
                log.model("Model moved to RAM (CPU)")

    def _move_to_gpu(self) -> None:
        with self.lock:
            if self.model is not None and self.current_device == "cpu" and self.preferred_device == "cuda":
                log.model("Moving model RAM -> VRAM (CPU -> GPU)...")
                self.model = None
                gc.collect()
                try:
                    self.model = WhisperModel(self.model_size, device="cuda", compute_type=self.gpu_compute_type)
                    self.current_device = "cuda"
                    log.model("Model moved to VRAM (GPU)")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.warn(f"GPU move failed: {e} - keeping on CPU")
                    self.model = WhisperModel(self.model_size, device="cpu", compute_type=self.cpu_compute_type)
                    self.current_device = "cpu"

    def _schedule_memory_management(self) -> None:
        self._cancel_all_timers()
        if self.current_device == "cuda":
            self.ram_timer = threading.Timer(self.move_to_ram_after_seconds, self._auto_move_to_ram)
            self.ram_timer.daemon = True
            self.ram_timer.start()
        elif self.current_device == "cpu":
            self.disk_timer = threading.Timer(self.unload_after_seconds, self._auto_unload)
            self.disk_timer.daemon = True
            self.disk_timer.start()

    def _cancel_all_timers(self) -> None:
        if self.ram_timer is not None:
            self.ram_timer.cancel()
            self.ram_timer = None
        if self.disk_timer is not None:
            self.disk_timer.cancel()
            self.disk_timer = None

    def _auto_move_to_ram(self) -> None:
        if not self.keep_model_loaded:
            self._move_to_cpu()
            self.disk_timer = threading.Timer(self.unload_after_seconds, self._auto_unload)
            self.disk_timer.daemon = True
            self.disk_timer.start()

    def _auto_unload(self) -> None:
        if not self.keep_model_loaded:
            self.unload_model()

    def _preload_worker(self) -> None:
        try:
            self.load_model()
        finally:
            self.is_preloading = False
