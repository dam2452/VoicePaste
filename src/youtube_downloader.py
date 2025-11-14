import re
import tempfile
import os
import numpy as np
import yt_dlp
from scipy.io import wavfile
from typing import Optional, Tuple


class YouTubeDownloader:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    def is_youtube_url(self, url: str) -> bool:
        youtube_patterns = [
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
            r'(https?://)?(www\.)?youtu\.be/'
        ]
        return any(re.match(pattern, url) for pattern in youtube_patterns)

    def download_audio(self, url: str) -> Optional[Tuple[np.ndarray, str]]:
        if not self.is_youtube_url(url):
            print(f"URL is not a YouTube link: {url}")
            return None

        temp_audio_path = os.path.join(self.temp_dir, 'voicepaste_yt_audio.wav')

        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except Exception:
            pass

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'outtmpl': temp_audio_path.replace('.wav', ''),
            'quiet': True,
            'no_warnings': True,
        }

        try:
            print(f"Downloading audio from YouTube: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Unknown')
                print(f"Downloaded: {title}")

            if not os.path.exists(temp_audio_path):
                print(f"Audio file not found: {temp_audio_path}")
                return None

            print("Converting audio to 16kHz mono...")
            sample_rate, audio = wavfile.read(temp_audio_path)

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

            try:
                os.remove(temp_audio_path)
            except Exception:
                pass

            print(f"Audio converted: {len(audio)/sample_rate:.1f}s @ {sample_rate}Hz")
            return audio.astype(np.float32), title

        except Exception as e:
            print(f"Error downloading YouTube audio: {e}")
            try:
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
            except Exception:
                pass
            return None

    def cleanup(self):
        temp_audio_path = os.path.join(self.temp_dir, 'voicepaste_yt_audio.wav')
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except Exception:
            pass
