import threading
from typing import Optional

import numpy as np
import pyaudio
from scipy import signal

from src import log


class AudioRecorder:
    def __init__(self, target_sample_rate: int = 16000, device_id: Optional[int] = None):
        self.target_sample_rate = target_sample_rate
        self.is_recording = False
        self.audio_data = []
        self.stream = None
        self.lock = threading.Lock()
        self.pyaudio_instance = pyaudio.PyAudio()
        self.device_id = device_id if device_id is not None else self._find_input_device()

        self.device_sample_rate = self._get_device_sample_rate()
        log.audio_info(f"Native: {self.device_sample_rate} Hz -> Whisper: {self.target_sample_rate} Hz")

    def _find_input_device(self) -> Optional[int]:
        # pylint: disable=too-many-try-statements
        try:
            nvidia_broadcast_device = None
            first_input_device = None

            for i in range(self.pyaudio_instance.get_device_count()):
                device_info = self.pyaudio_instance.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    if first_input_device is None:
                        first_input_device = i

                    if 'NVIDIA Broadcast' in device_info['name'] or 'nvidia broadcast' in device_info['name'].lower():
                        nvidia_broadcast_device = i
                        log.audio_info(f"Auto-detected NVIDIA Broadcast: {device_info['name']}")
                        return nvidia_broadcast_device

            if first_input_device is not None:
                device_info = self.pyaudio_instance.get_device_info_by_index(first_input_device)
                log.audio_info(f"Auto-detected input device: {device_info['name']}")
                return first_input_device

            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Error finding input device: {e}")
            return None

    def _get_device_sample_rate(self) -> int:
        if self.device_id is None:
            return self.target_sample_rate

        try:
            device_info = self.pyaudio_instance.get_device_info_by_index(self.device_id)
            native_rate = int(device_info['defaultSampleRate'])
            return native_rate
        except Exception:  # pylint: disable=broad-exception-caught
            return 48000

    def start_recording(self):
        with self.lock:
            if self.is_recording:
                return
            self.is_recording = True
            self.audio_data = []

        if self.device_id is None:
            raise RuntimeError("No input device found. Please check your microphone connection.")

        try:
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.device_sample_rate,
                input=True,
                input_device_index=self.device_id,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback,
            )
            self.stream.start_stream()
        except Exception as e:
            self.is_recording = False
            log.error("Failed to start recording. Available devices:")
            for i in range(self.pyaudio_instance.get_device_count()):
                info = self.pyaudio_instance.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    log.audio_info(f"  [{i}] {info['name']}")
            raise RuntimeError(f"Failed to start audio recording: {e}") from e

    def stop_recording(self) -> Optional[np.ndarray]:
        with self.lock:
            if not self.is_recording:
                return None
            self.is_recording = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.audio_data:
            audio_np = np.frombuffer(b''.join(self.audio_data), dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0

            if self.device_sample_rate != self.target_sample_rate:
                num_samples = int(len(audio_float) * self.target_sample_rate / self.device_sample_rate)
                audio_float = signal.resample(audio_float, num_samples)

            return audio_float
        return None

    def _audio_callback(self, in_data, frame_count, time_info, status):  # pylint: disable=unused-argument
        if self.is_recording:
            self.audio_data.append(in_data)
        return in_data, pyaudio.paContinue

    def get_available_devices(self):
        devices = []
        for i in range(self.pyaudio_instance.get_device_count()):
            info = self.pyaudio_instance.get_device_info_by_index(i)
            devices.append(info)
        return devices

    def get_device_info(self):
        try:
            if self.device_id is not None:
                return self.pyaudio_instance.get_device_info_by_index(self.device_id)
            return None
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def __del__(self):
        if hasattr(self, 'pyaudio_instance'):
            self.pyaudio_instance.terminate()
