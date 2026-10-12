import time

import numpy as np
import pytest

from src.infrastructure.system.audio_recorder import AudioRecorder


def test_audio_recorder_initialization():
    recorder = AudioRecorder(target_sample_rate=16000)
    assert recorder._target_sample_rate == 16000
    assert recorder._is_recording is False
    assert not recorder._audio_data


def test_audio_recorder_initialization_with_device():
    recorder = AudioRecorder(target_sample_rate=16000, device_id=6)
    assert recorder._target_sample_rate == 16000
    assert recorder._device_id == 6


def test_audio_recorder_device_info():
    recorder = AudioRecorder(target_sample_rate=16000)
    device_info = recorder.get_device_info()
    if device_info:
        assert 'name' in device_info
        assert 'max_input_channels' in device_info


@pytest.mark.skipif(True, reason="Requires actual audio device")
def test_start_stop_recording():
    recorder = AudioRecorder(target_sample_rate=16000)
    if recorder._device_id is None:
        pytest.skip("No audio input device found")

    recorder.start_recording()
    assert recorder._is_recording is True

    time.sleep(0.5)

    audio_data = recorder.stop_recording()
    assert recorder._is_recording is False
    assert audio_data is not None
    assert isinstance(audio_data.data, np.ndarray)
    assert len(audio_data.data) > 0


@pytest.mark.skipif(True, reason="Requires actual audio device")
def test_multiple_recordings():
    recorder = AudioRecorder(target_sample_rate=16000)
    if recorder._device_id is None:
        pytest.skip("No audio input device found")

    recorder.start_recording()
    time.sleep(0.3)
    data1 = recorder.stop_recording()

    recorder.start_recording()
    time.sleep(0.3)
    data2 = recorder.stop_recording()

    assert data1 is not None
    assert data2 is not None
