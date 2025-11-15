import re
import tempfile
import numpy as np
from pathlib import Path
import yt_dlp
from scipy.io import wavfile
from typing import Optional, Tuple


class YouTubeDownloader:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir())

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        youtube_patterns = [
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
            r'(https?://)?(www\.)?youtu\.be/'
        ]
        return any(re.match(pattern, url) for pattern in youtube_patterns)

    def download_audio(self, url: str) -> Optional[Tuple[np.ndarray, str]]:
        if not self.is_youtube_url(url):
            print(f"URL is not a YouTube link: {url}")
            return None

        temp_audio_path = self.temp_dir / 'voicepaste_yt_audio.wav'

        # noinspection PyBroadException
        try:
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except Exception:
            pass

        ydl_opts = {
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': str(temp_audio_path.with_suffix('')),
            'quiet': True,
            'no_warnings': True,
            'cookiesfrombrowser': ('firefox',),
            'js_runtimes': {'node': {}},
        }

        try:
            print(f"Downloading audio from YouTube: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Unknown')
                print(f"Downloaded: {title}")

            if not temp_audio_path.exists():
                print(f"Audio file not found: {temp_audio_path}")
                return None

            print("Converting audio to 16kHz mono...")
            sample_rate, audio = wavfile.read(str(temp_audio_path))

            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.int32:
                audio = audio.astype(np.float32) / 2147483648.0

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            if sample_rate != 16000:
                from scipy.signal import resample
                num_samples = int(len(audio) * 16000 / sample_rate)
                audio = resample(audio, num_samples)
                sample_rate = 16000

            # noinspection PyBroadException
            try:
                temp_audio_path.unlink()
            except Exception:
                pass

            print(f"Audio converted: {len(audio)/sample_rate:.1f}s @ {sample_rate}Hz")
            return audio.astype(np.float32), title

        except Exception as e:
            print(f"Error downloading YouTube audio: {e}")
            # noinspection PyBroadException
            try:
                if temp_audio_path.exists():
                    temp_audio_path.unlink()
            except Exception:
                pass
            return None

    def cleanup(self):
        temp_audio_path = self.temp_dir / 'voicepaste_yt_audio.wav'
        # noinspection PyBroadException
        try:
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except Exception:
            pass
