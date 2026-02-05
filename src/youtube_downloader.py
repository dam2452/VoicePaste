from pathlib import Path
import re
import tempfile
from typing import (
    Optional,
    Tuple,
)

import numpy as np
from scipy.io import wavfile
import yt_dlp

from src.audio_utils import normalize_audio


class YouTubeDownloader:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir())

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        youtube_patterns = [
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
            r'(https?://)?(www\.)?youtu\.be/',
        ]
        return any(re.match(pattern, url) for pattern in youtube_patterns)

    def download_audio(self, url: str) -> Optional[Tuple[np.ndarray, str]]:
        if not self.is_youtube_url(url):
            print(f"URL is not a YouTube link: {url}")
            return None

        temp_audio_path = self.temp_dir / 'voicepaste_yt_audio.wav'

        try:
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': str(temp_audio_path.with_suffix('')),
            'quiet': True,
            'no_warnings': True,
        }

        # pylint: disable=too-many-try-statements
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
            audio, sample_rate = normalize_audio(audio, sample_rate, 16000)

            try:
                temp_audio_path.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

            print(f"Audio converted: {len(audio)/sample_rate:.1f}s @ {sample_rate}Hz")
            return audio, title

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error downloading YouTube audio: {e}")
            try:
                if temp_audio_path.exists():
                    temp_audio_path.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            return None

    def cleanup(self):
        temp_audio_path = self.temp_dir / 'voicepaste_yt_audio.wav'
        try:
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
