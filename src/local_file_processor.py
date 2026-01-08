from pathlib import Path
import subprocess
import sys
import tempfile
from typing import (
    Optional,
    Tuple,
)

import numpy as np
from scipy.io import wavfile

from src.audio_utils import normalize_audio


class LocalFileProcessor:
    SUPPORTED_AUDIO = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
    SUPPORTED_VIDEO = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}

    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir())

    def is_valid_file_path(self, path: str) -> bool:
        if not path or not isinstance(path, str):
            return False

        path_str = path.strip().strip('"').strip("'")
        file_path = Path(path_str)

        if not file_path.is_file():
            return False

        ext = file_path.suffix.lower()
        return ext in self.SUPPORTED_AUDIO or ext in self.SUPPORTED_VIDEO

    def process_file(self, file_path: str) -> Optional[Tuple[np.ndarray, str]]:  # pylint: disable=too-many-statements
        file_path_str = file_path.strip().strip('"').strip("'")

        if not self.is_valid_file_path(file_path_str):
            print(f"Invalid or unsupported file: {file_path_str}")
            return None

        file_path = Path(file_path_str)
        temp_wav_path = self.temp_dir / 'voicepaste_local_audio.wav'

        try:
            if temp_wav_path.exists():
                temp_wav_path.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        ext = file_path.suffix.lower()
        filename = file_path.name

        # pylint: disable=too-many-try-statements
        try:
            if ext in self.SUPPORTED_VIDEO or ext not in {'.wav'}:
                print("Extracting audio with FFmpeg...")
                sys.stdout.flush()
                result = subprocess.run(
                    [
                        'ffmpeg',
                        '-i', str(file_path),
                        '-vn',
                        '-acodec', 'pcm_s16le',
                        '-ar', '16000',
                        '-ac', '1',
                        '-y',
                        str(temp_wav_path),
                    ], capture_output=True, text=True, timeout=300, check=False,
                )

                if result.returncode != 0:
                    print(f"FFmpeg error: {result.stderr}")
                    sys.stdout.flush()
                    return None

                if not temp_wav_path.exists():
                    print(f"Audio extraction failed: {temp_wav_path} not created")
                    sys.stdout.flush()
                    return None

                sample_rate, audio = wavfile.read(str(temp_wav_path))
            else:
                print("Loading WAV file...")
                sys.stdout.flush()
                sample_rate, audio = wavfile.read(str(file_path))

            if sample_rate != 16000:
                print(f"Resampling from {sample_rate}Hz to 16000Hz...")
                sys.stdout.flush()

            audio, sample_rate = normalize_audio(audio, sample_rate, 16000)

            try:
                if temp_wav_path.exists() and file_path != temp_wav_path:
                    temp_wav_path.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

            duration = len(audio) / sample_rate
            print(f"Audio loaded: {duration:.1f}s @ {sample_rate}Hz")
            sys.stdout.flush()
            return audio, filename

        except subprocess.TimeoutExpired:
            print("FFmpeg timeout - file too large or processing error")
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error processing file: {e}")
            try:
                if temp_wav_path.exists():
                    temp_wav_path.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            return None

    def cleanup(self):
        temp_wav_path = self.temp_dir / 'voicepaste_local_audio.wav'
        try:
            if temp_wav_path.exists():
                temp_wav_path.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
