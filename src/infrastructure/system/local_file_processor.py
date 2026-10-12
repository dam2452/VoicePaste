from pathlib import Path
import subprocess
import tempfile
from typing import Optional

from scipy.io import wavfile

from src.core.dtos import AudioData
from src.audio_utils import normalize_audio
from src import log


class LocalFileProcessor:
    _SUPPORTED_AUDIO = frozenset({'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'})
    _SUPPORTED_VIDEO = frozenset({'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'})

    def __init__(self) -> None:
        self._temp_dir = Path(tempfile.gettempdir())

    def is_valid_path(self, path: str) -> bool:
        if not path or not isinstance(path, str):
            return False
        cleaned = path.strip().strip('"').strip("'")
        file_path = Path(cleaned)
        return file_path.is_file() and file_path.suffix.lower() in self._SUPPORTED_AUDIO | self._SUPPORTED_VIDEO

    def process(self, path: str) -> Optional[AudioData]:
        cleaned = path.strip().strip('"').strip("'")
        if not self.is_valid_path(cleaned):
            log.error(f"Invalid or unsupported file: {cleaned}")
            return None

        file_path = Path(cleaned)
        temp_wav = self._temp_dir / 'aitoys_local_audio.wav'
        ext = file_path.suffix.lower()
        filename = file_path.name

        try:
            if temp_wav.exists():
                temp_wav.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        # pylint: disable=too-many-try-statements
        try:
            if ext in self._SUPPORTED_VIDEO or ext != '.wav':
                log.audio_info(f"Extracting audio with FFmpeg: {filename}")
                result = subprocess.run(
                    ['ffmpeg', '-i', str(file_path), '-vn', '-acodec', 'pcm_s16le',
                     '-ar', '16000', '-ac', '1', '-y', str(temp_wav)],
                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                    timeout=300, check=False,
                )
                if result.returncode != 0:
                    log.error(f"FFmpeg error: {result.stderr[:200]}")
                    return None
                if not temp_wav.exists():
                    log.error("Audio extraction failed - output file not created")
                    return None
                sample_rate, audio = wavfile.read(str(temp_wav))
            else:
                log.audio_info(f"Loading WAV: {filename}")
                sample_rate, audio = wavfile.read(str(file_path))

            if sample_rate != 16000:
                log.audio_info(f"Resampling {sample_rate} Hz -> 16000 Hz")
            audio, sample_rate = normalize_audio(audio, sample_rate, 16000)

            try:
                if temp_wav.exists() and file_path != temp_wav:
                    temp_wav.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

            log.audio_info(f"Ready: {len(audio)/sample_rate:.1f}s @ {sample_rate} Hz")
            return AudioData(data=audio, sample_rate=sample_rate, source_name=filename)

        except subprocess.TimeoutExpired:
            log.error("FFmpeg timeout - file too large or processing error")
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"File processing error: {e}")
            try:
                if temp_wav.exists():
                    temp_wav.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            return None

    def cleanup(self) -> None:
        temp_wav = self._temp_dir / 'aitoys_local_audio.wav'
        try:
            if temp_wav.exists():
                temp_wav.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
