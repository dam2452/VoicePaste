import io
import wave
from unittest.mock import MagicMock, patch, mock_open

from src.infrastructure.ai.tts_engine import TTSEngine


def _make_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b'\x00\x00' * 2400)
    return buf.getvalue()


def test_tts_engine_defaults():
    e = TTSEngine()
    assert e._backend == "edge_tts"
    assert e._voice == "en-US-AriaNeural"
    assert e.is_speaking is False


def test_tts_engine_configure():
    e = TTSEngine()
    e.configure(backend="openai", api_url="http://api/v1/", api_key="k", model="omnivoice", voice="auto")
    assert e._backend == "openai"
    assert e._api_url == "http://api/v1"
    assert e._api_key == "k"
    assert e._model == "omnivoice"
    assert e._voice == "auto"


def test_tts_engine_stop_when_idle():
    e = TTSEngine()
    e.stop()
    assert e.is_speaking is False


def test_tts_engine_stop_closes_stream():
    e = TTSEngine()
    e._is_speaking = True
    mock_stream = MagicMock()
    e._stream = mock_stream
    e.stop()
    mock_stream.stop_stream.assert_called_once()
    mock_stream.close.assert_called_once()
    assert e.is_speaking is False


def test_tts_engine_speak_openai():
    wav_data = _make_wav_bytes()
    e = TTSEngine()
    e.configure(backend="openai", api_url="http://localhost:5959/v1", api_key="", model="omnivoice", voice="auto")

    mock_resp = MagicMock()
    mock_resp.content = wav_data
    mock_resp.raise_for_status = MagicMock()

    mock_stream = MagicMock()

    with patch("src.infrastructure.ai.tts_engine.requests") as mock_requests, \
         patch("src.infrastructure.ai.tts_engine.sd.RawOutputStream", return_value=mock_stream):

        mock_requests.post.return_value = mock_resp
        e.speak("test text")

    assert e.is_speaking is False
    mock_requests.post.assert_called_once()
    call_json = mock_requests.post.call_args[1]["json"]
    assert call_json["model"] == "omnivoice"
    assert call_json["voice"] == "auto"
    assert call_json["input"] == "test text"


def test_tts_engine_shutdown():
    e = TTSEngine()
    e.shutdown()  # nothing to crash on without pyaudio
    assert e._stream is None
