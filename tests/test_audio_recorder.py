import pytest
import time
import numpy as np
from src.audio_recorder import AudioRecorder


def test_audio_recorder_initialization():
    recorder = AudioRecorder(target_sample_rate=16000)
    assert recorder.target_sample_rate == 16000
    assert recorder.is_recording is False
    assert recorder.audio_data == []
    recorder.pyaudio_instance.terminate()


def test_audio_recorder_initialization_with_device():
    recorder = AudioRecorder(target_sample_rate=16000, device_id=6)
    assert recorder.target_sample_rate == 16000
    assert recorder.device_id == 6
    recorder.pyaudio_instance.terminate()


def test_audio_recorder_device_info():
    recorder = AudioRecorder(target_sample_rate=16000)
    device_info = recorder.get_device_info()
    if device_info:
        assert 'name' in device_info
        assert 'maxInputChannels' in device_info
    recorder.pyaudio_instance.terminate()


def test_audio_recorder_available_devices():
    recorder = AudioRecorder(target_sample_rate=16000)
    devices = recorder.get_available_devices()
    assert devices is not None
    assert len(devices) > 0
    recorder.pyaudio_instance.terminate()


@pytest.mark.skipif(True, reason="Requires actual audio device")
def test_start_stop_recording():
    recorder = AudioRecorder(target_sample_rate=16000)
    if recorder.device_id is None:
        pytest.skip("No audio input device found")

    recorder.start_recording()
    assert recorder.is_recording is True

    time.sleep(0.5)

    audio_data = recorder.stop_recording()
    assert recorder.is_recording is False
    assert audio_data is not None
    assert isinstance(audio_data, np.ndarray)
    assert len(audio_data) > 0


@pytest.mark.skipif(True, reason="Requires actual audio device")
def test_multiple_recordings():
    recorder = AudioRecorder(target_sample_rate=16000)
    if recorder.device_id is None:
        pytest.skip("No audio input device found")

    recorder.start_recording()
    time.sleep(0.3)
    data1 = recorder.stop_recording()

    recorder.start_recording()
    time.sleep(0.3)
    data2 = recorder.stop_recording()

    assert data1 is not None
    assert data2 is not None
    assert len(data1) > 0
    assert len(data2) > 0
