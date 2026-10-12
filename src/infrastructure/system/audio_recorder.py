import threading
from typing import Dict, Optional

import numpy as np
import sounddevice as sd
from scipy import signal

from src.core.dtos import AudioData
from src import log


class AudioRecorder:
    def __init__(self, target_sample_rate: int = 16000, device_id: Optional[int] = None):
        self._target_sample_rate = target_sample_rate
        self._is_recording = False
        self._audio_data = []
        self._stream = None
        self._lock = threading.Lock()
        self._device_id = device_id if device_id is not None else self._find_input_device()
        self.device_sample_rate = self._get_device_sample_rate()
        log.audio_info(f"Native: {self.device_sample_rate} Hz -> Whisper: {self._target_sample_rate} Hz")

    def get_device_info(self) -> Optional[Dict]:
        try:
            if self._device_id is not None:
                return sd.query_devices(self._device_id)
            return None
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def start_recording(self) -> None:
        with self._lock:
            if self._is_recording:
                return
            self._is_recording = True
            self._audio_data = []

        if self._device_id is None:
            raise RuntimeError("No input device found. Please check your microphone connection.")

        try:
            self._stream = sd.RawInputStream(
                samplerate=self.device_sample_rate,
                blocksize=1024,
                dtype="int16",
                channels=1,
                device=self._device_id,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            self._is_recording = False
            log.error("Failed to start recording. Available devices:")
            for i, info in enumerate(sd.query_devices()):
                if info['max_input_channels'] > 0:
                    log.audio_info(f"  [{i}] {info['name']}")
            raise RuntimeError(f"Failed to start audio recording: {e}") from e

    def stop_recording(self) -> Optional[AudioData]:
        with self._lock:
            if not self._is_recording:
                return None
            self._is_recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._audio_data:
            return None

        audio_np = np.frombuffer(b''.join(self._audio_data), dtype=np.int16)
        audio_float = audio_np.astype(np.float32) / 32768.0

        if self.device_sample_rate != self._target_sample_rate:
            num_samples = int(len(audio_float) * self._target_sample_rate / self.device_sample_rate)
            audio_float = signal.resample(audio_float, num_samples)

        return AudioData(data=audio_float, sample_rate=self._target_sample_rate, source_name="microphone")

    def _audio_callback(self, indata, frames, time_info, status):  # pylint: disable=unused-argument
        if status:
            log.audio_info(f"Recording status: {status}")
        if self._is_recording:
            self._audio_data.append(bytes(indata))

    def _find_input_device(self) -> Optional[int]:
        # pylint: disable=too-many-try-statements
        try:
            first_input = None
            for i, info in enumerate(sd.query_devices()):
                if info['max_input_channels'] > 0:
                    if first_input is None:
                        first_input = i
                    name = info['name']
                    if 'NVIDIA Broadcast' in name or 'nvidia broadcast' in name.lower():
                        log.audio_info(f"Auto-detected NVIDIA Broadcast: {name}")
                        return i
            if first_input is not None:
                log.audio_info(f"Auto-detected input device: {sd.query_devices(first_input)['name']}")
            return first_input
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Error finding input device: {e}")
            return None

    def _get_device_sample_rate(self) -> int:
        if self._device_id is None:
            return self._target_sample_rate
        try:
            return int(sd.query_devices(self._device_id)['default_samplerate'])
        except Exception:  # pylint: disable=broad-exception-caught
            return 48000
