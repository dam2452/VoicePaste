import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from scipy.signal import resample
import subprocess
from typing import Optional, Tuple


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

    def process_file(self, file_path: str) -> Optional[Tuple[np.ndarray, str]]:
        file_path_str = file_path.strip().strip('"').strip("'")

        if not self.is_valid_file_path(file_path_str):
            print(f"Invalid or unsupported file: {file_path_str}")
            return None

        file_path = Path(file_path_str)
        temp_wav_path = self.temp_dir / 'voicepaste_local_audio.wav'

        # noinspection PyBroadException
        try:
            if temp_wav_path.exists():
                temp_wav_path.unlink()
        except Exception:
            pass

        ext = file_path.suffix.lower()
        filename = file_path.name

        try:
            print(f"Processing file: {filename}")

            if ext in self.SUPPORTED_VIDEO or ext not in {'.wav'}:
                print("Extracting audio with FFmpeg...")
                result = subprocess.run([
                    'ffmpeg',
                    '-i', str(file_path),
                    '-vn',
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',
                    '-ac', '1',
                    '-y',
                    str(temp_wav_path)
                ], capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    print(f"FFmpeg error: {result.stderr}")
                    return None

                if not temp_wav_path.exists():
                    print(f"Audio extraction failed: {temp_wav_path} not created")
                    return None

                sample_rate, audio = wavfile.read(str(temp_wav_path))
            else:
                print("Loading WAV file...")
                sample_rate, audio = wavfile.read(str(file_path))

            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.int32:
                audio = audio.astype(np.float32) / 2147483648.0

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            if sample_rate != 16000:
                print(f"Resampling from {sample_rate}Hz to 16000Hz...")
                num_samples = int(len(audio) * 16000 / sample_rate)
                audio = resample(audio, num_samples)
                sample_rate = 16000

            # noinspection PyBroadException
            try:
                if temp_wav_path.exists() and file_path != temp_wav_path:
                    temp_wav_path.unlink()
            except Exception:
                pass

            duration = len(audio) / sample_rate
            print(f"Audio loaded: {duration:.1f}s @ {sample_rate}Hz")
            return audio.astype(np.float32), filename

        except subprocess.TimeoutExpired:
            print("FFmpeg timeout - file too large or processing error")
            return None
        except Exception as e:
            print(f"Error processing file: {e}")
            # noinspection PyBroadException
            try:
                if temp_wav_path.exists():
                    temp_wav_path.unlink()
            except Exception:
                pass
            return None

    def cleanup(self):
        temp_wav_path = self.temp_dir / 'voicepaste_local_audio.wav'
        # noinspection PyBroadException
        try:
            if temp_wav_path.exists():
                temp_wav_path.unlink()
        except Exception:
            pass
