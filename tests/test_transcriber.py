import pytest
import numpy as np
import time
from src.transcriber import Transcriber


def test_transcriber_initialization():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    assert transcriber.model_size == "tiny"
    assert transcriber.preferred_device == "cpu"
    assert transcriber.gpu_compute_type == "int8"
    assert transcriber.cpu_compute_type == "int8"
    assert transcriber.model is None
    assert transcriber.current_device is None
    assert transcriber.keep_model_loaded is False
    assert transcriber.move_to_ram_after_seconds == 3600
    assert transcriber.unload_after_seconds == 18000
    assert transcriber.is_preloading is False
    assert transcriber.preload_thread is None


def test_transcriber_initialization_with_custom_timers():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        move_to_ram_after_seconds=60,
        unload_after_seconds=120
    )
    assert transcriber.move_to_ram_after_seconds == 60
    assert transcriber.unload_after_seconds == 120


def test_transcriber_initialization_with_keep_loaded():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        keep_model_loaded=True
    )
    assert transcriber.keep_model_loaded is True


def test_transcriber_load_model():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model()
    assert transcriber.model is not None
    assert transcriber.current_device == "cpu"
    transcriber.shutdown()


def test_transcriber_load_model_on_target_device():
    transcriber = Transcriber(model_size="tiny", device="cuda", compute_type="float16")
    transcriber.load_model(target_device="cpu")
    assert transcriber.model is not None
    assert transcriber.current_device == "cpu"
    transcriber.shutdown()


def test_transcriber_unload_model():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model()
    assert transcriber.model is not None
    assert transcriber.current_device == "cpu"
    transcriber.unload_model()
    assert transcriber.model is None
    assert transcriber.current_device is None


def test_transcriber_shutdown():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model()
    assert transcriber.model is not None
    transcriber.shutdown()
    assert transcriber.model is None
    assert transcriber.current_device is None


def test_transcriber_move_to_cpu():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model(target_device="cpu")
    transcriber.current_device = "cuda"
    transcriber._move_to_cpu()
    assert transcriber.current_device == "cpu"
    assert transcriber.model is not None
    transcriber.shutdown()


def test_transcriber_timers_cancelled_on_shutdown():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        move_to_ram_after_seconds=1,
        unload_after_seconds=2
    )
    transcriber.load_model()
    transcriber._schedule_memory_management()
    assert transcriber.disk_timer is not None
    transcriber.shutdown()
    assert transcriber.ram_timer is None
    assert transcriber.disk_timer is None


def test_transcriber_schedule_memory_management_cpu():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        move_to_ram_after_seconds=60,
        unload_after_seconds=120
    )
    transcriber.load_model()
    transcriber._schedule_memory_management()
    assert transcriber.ram_timer is None
    assert transcriber.disk_timer is not None
    transcriber.shutdown()


def test_transcriber_auto_move_to_ram():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        move_to_ram_after_seconds=1,
        unload_after_seconds=2
    )
    transcriber.load_model()
    transcriber.current_device = "cuda"
    transcriber._auto_move_to_ram()
    assert transcriber.current_device == "cpu"
    assert transcriber.model is not None
    assert transcriber.disk_timer is not None
    transcriber.shutdown()


def test_transcriber_auto_unload():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8"
    )
    transcriber.load_model()
    assert transcriber.model is not None
    transcriber._auto_unload()
    assert transcriber.model is None
    assert transcriber.current_device is None


def test_transcriber_keep_model_loaded_prevents_unload():
    transcriber = Transcriber(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        keep_model_loaded=True
    )
    transcriber.load_model()
    assert transcriber.model is not None
    transcriber._auto_unload()
    assert transcriber.model is not None
    transcriber.shutdown()


def test_transcriber_preload_for_recording_when_model_none():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    assert transcriber.model is None
    transcriber.preload_for_recording()
    assert transcriber.is_preloading is True
    assert transcriber.preload_thread is not None
    transcriber.preload_thread.join(timeout=10)
    assert transcriber.model is not None
    transcriber.shutdown()


def test_transcriber_preload_for_recording_when_already_preloading():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.is_preloading = True
    transcriber.preload_for_recording()
    assert transcriber.preload_thread is None
    transcriber.shutdown()


def test_transcriber_preload_for_recording_when_on_cpu():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model()
    transcriber.current_device = "cpu"
    transcriber.preferred_device = "cuda"
    transcriber.preload_for_recording()
    assert transcriber.is_preloading is True
    assert transcriber.preload_thread is not None
    transcriber.shutdown()


def test_transcriber_shutdown_waits_for_preload():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.preload_for_recording()
    assert transcriber.is_preloading is True
    transcriber.shutdown()
    assert transcriber.model is None


@pytest.mark.skipif(True, reason="Requires actual audio data and model")
def test_transcribe():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    dummy_audio = np.random.randn(16000).astype(np.float32)
    result = transcriber.transcribe(dummy_audio)
    assert isinstance(result, str)
    transcriber.shutdown()
