from pathlib import Path
import re
import tempfile
from typing import Optional

from scipy.io import wavfile
import yt_dlp

from src.core.dtos import AudioData
from src.audio_utils import normalize_audio
from src import log


class YtDlpDownloader:
    def __init__(self, cookies_from_browser: str = "firefox") -> None:
        self._temp_dir = Path(tempfile.gettempdir())
        self._cookies_from_browser = cookies_from_browser

    @staticmethod
    def is_valid_url(url: str) -> bool:
        patterns = [
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
            r'(https?://)?(www\.)?youtu\.be/',
        ]
        return any(re.match(p, url) for p in patterns)

    def download_audio(self, url: str) -> Optional[AudioData]:
        if not self.is_valid_url(url):
            log.warn(f"Not a YouTube URL: [dim]{url}[/dim]")
            return None

        temp_path = self._temp_dir / 'aitoys_yt_audio.wav'
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
            'outtmpl': str(temp_path.with_suffix('')),
            'quiet': True,
            'no_warnings': True,
            # YouTube wymaga solvera n-challenge; domyślny runtime to deno, którego nie ma
            'js_runtimes': {'node': {}},
        }
        if self._cookies_from_browser:
            ydl_opts['cookiesfrombrowser'] = (self._cookies_from_browser,)

        # pylint: disable=too-many-try-statements
        try:
            log.info(f"Downloading: [dim]{url}[/dim]")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Unknown')
                log.info(f"Downloaded: [italic]{title}[/italic]")

            if not temp_path.exists():
                log.error(f"Audio file not found: {temp_path}")
                return None

            log.audio_info("Converting to 16 kHz mono...")
            sample_rate, audio = wavfile.read(str(temp_path))
            audio, sample_rate = normalize_audio(audio, sample_rate, 16000)

            try:
                temp_path.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

            log.audio_info(f"Ready: {len(audio)/sample_rate:.1f}s @ {sample_rate} Hz")
            return AudioData(data=audio, sample_rate=sample_rate, source_name=title)

        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"YouTube download error: {e}")
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            return None

    def cleanup(self) -> None:
        temp_path = self._temp_dir / 'aitoys_yt_audio.wav'
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
