import pytest
import numpy as np
from src.transcriber import Transcriber


def test_transcriber_initialization():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    assert transcriber.model_size == "tiny"
    assert transcriber.device == "cpu"
    assert transcriber.compute_type == "int8"
    assert transcriber.model is None
    assert transcriber.keep_model_loaded is False
    assert transcriber.unload_after_seconds == 1800


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
    transcriber.shutdown()


def test_transcriber_unload_model():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model()
    assert transcriber.model is not None
    transcriber.unload_model()
    assert transcriber.model is None


def test_transcriber_shutdown():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    transcriber.load_model()
    assert transcriber.model is not None
    transcriber.shutdown()
    assert transcriber.model is None


@pytest.mark.skipif(True, reason="Requires actual audio data and model")
def test_transcribe():
    transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
    dummy_audio = np.random.randn(16000).astype(np.float32)
    result = transcriber.transcribe(dummy_audio)
    assert isinstance(result, str)
    transcriber.shutdown()
