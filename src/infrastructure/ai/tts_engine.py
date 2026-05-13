import asyncio
import io
import tempfile
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pyaudio
import requests
from requests.exceptions import ConnectionError as RequestsConnectionError

from src import log


class TTSBackend(ABC):
    @abstractmethod
    def generate_audio(self, text: str) -> bytes:
        pass

    @abstractmethod
    def audio_format(self) -> str:
        pass


class EdgeTTSBackend(TTSBackend):
    def __init__(self, voice: str = "en-US-AriaNeural"):
        self._voice = voice

    def generate_audio(self, text: str) -> bytes:
        import edge_tts

        buf = io.BytesIO()

        async def _generate() -> None:
            communicate = edge_tts.Communicate(text, self._voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])

        asyncio.run(_generate())
        return buf.getvalue()

    def audio_format(self) -> str:
        return ".mp3"


class OpenAICompatibleBackend(TTSBackend):
    def __init__(self, api_url: str, api_key: str = "", model: str = "", voice: str = ""):
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._voice = voice

    def generate_audio(self, text: str) -> bytes:
        url = f"{self._api_url}/audio/speech"
        headers: dict = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {"model": self._model, "voice": self._voice, "input": text}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
        except RequestsConnectionError as exc:
            raise RuntimeError(
                f"Cannot connect to TTS server at {self._api_url}. "
                "Make sure the service is running."
            ) from exc
        response.raise_for_status()
        return response.content

    def audio_format(self) -> str:
        return ".wav"


class GeminiTTSBackend(TTSBackend):
    _SAMPLE_RATE = 24000
    _SAMPLE_WIDTH = 2
    _CHANNELS = 1

    def __init__(self, api_key: str, voice: str = "Kore",
                 model: str = "gemini-2.5-flash-preview-tts"):
        self._api_key = api_key
        self._voice = voice
        self._model = model

    def generate_audio(self, text: str) -> bytes:
        from google import genai  # pylint: disable=no-name-in-module
        from google.genai import types  # pylint: disable=no-name-in-module

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model=self._model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self._voice,
                        )
                    )
                ),
            ),
        )
        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        return self._pcm_to_wav(pcm_data)

    def _pcm_to_wav(self, pcm: bytes) -> bytes:
        buf = io.BytesIO()
        wf = wave.open(buf, "wb")
        wf.setnchannels(self._CHANNELS)
        wf.setsampwidth(self._SAMPLE_WIDTH)
        wf.setframerate(self._SAMPLE_RATE)
        wf.writeframes(pcm)
        wf.close()
        return buf.getvalue()

    def audio_format(self) -> str:
        return ".wav"


class TTSEngine:
    def __init__(self) -> None:
        self._backend: Optional[TTSBackend] = None
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream = None

    def set_backend(self, backend: TTSBackend) -> None:
        self._backend = backend

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak(self, text: str) -> None:
        with self._lock:
            if self._is_speaking:
                return

        if self._backend is None:
            raise RuntimeError("No TTS backend configured. Call set_backend() first.")

        self._stop_event.clear()
        self._playback_thread = threading.Thread(
            target=self._speak_worker, args=(text,), daemon=True
        )
        self._playback_thread.start()
        self._playback_thread.join()

    def stop(self) -> None:
        if not self._is_speaking:
            return
        self._stop_event.set()
        self._close_stream()
        with self._lock:
            self._is_speaking = False

    def shutdown(self) -> None:
        self.stop()
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None

    def _speak_worker(self, text: str) -> None:
        with self._lock:
            self._is_speaking = True

        try:
            audio_bytes = self._backend.generate_audio(text)  # type: ignore[union-attr]
            ext = self._backend.audio_format()  # type: ignore[union-attr]

            if self._stop_event.is_set():
                return

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            self._play_file(tmp_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            log.error(f"TTS error: {exc}")
            with self._lock:
                self._is_speaking = False

    def _get_pyaudio(self) -> pyaudio.PyAudio:
        if not self._pyaudio:
            self._pyaudio = pyaudio.PyAudio()
        return self._pyaudio

    def _close_stream(self) -> None:
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._stream = None

    def _play_file(self, path: str) -> None:
        p = self._get_pyaudio()
        try:
            self._stream_wav(p, path)
        finally:
            self._close_stream()
            with self._lock:
                self._is_speaking = False
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    def _stream_wav(self, p: pyaudio.PyAudio, path: str) -> None:
        with wave.open(path, "rb") as wf:
            frames_per_chunk = int(wf.getframerate() * 0.1)
            self._stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            while not self._stop_event.is_set():
                data = wf.readframes(frames_per_chunk)
                if not data:
                    break
                self._stream.write(data)
