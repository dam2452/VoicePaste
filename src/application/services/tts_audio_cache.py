import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from src import log


class TTSAudioCache:
    _TTL = 604800  # 7 days
    _CACHE_DIR = Path.home() / '.aitoys_tts_cache'
    _INDEX_FILE = _CACHE_DIR / 'index.json'

    def __init__(self) -> None:
        self._index: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._cleanup_timer: Optional[threading.Timer] = None
        self._CACHE_DIR.mkdir(exist_ok=True)
        self._load_index()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[Path]:
        key = self._hash(text)
        with self._lock:
            ts = self._index.get(key)
            if ts is None:
                return None
            if time.time() - ts >= self._TTL:
                self._evict(key)
                return None
            path = self._CACHE_DIR / f"{key}.wav"
            if not path.exists():
                del self._index[key]
                self._save_index()
                return None
            log.info(f"TTS cache hit: [dim]{key[:12]}...[/dim]")
            return path

    def put(self, text: str, audio_bytes: bytes, ext: str = ".wav") -> Path:
        key = self._hash(text)
        path = self._CACHE_DIR / f"{key}{ext}"
        path.write_bytes(audio_bytes)
        with self._lock:
            self._index[key] = time.time()
            self._save_index()
        self._schedule_cleanup()
        return path

    def shutdown(self) -> None:
        if self._cleanup_timer:
            self._cleanup_timer.cancel()

    def _evict(self, key: str) -> None:
        audio = self._CACHE_DIR / f"{key}.wav"
        try:
            audio.unlink(missing_ok=True)
        except OSError:
            pass
        if key in self._index:
            del self._index[key]
        self._save_index()

    def _schedule_cleanup(self) -> None:
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        self._cleanup_timer = threading.Timer(self._TTL, self._cleanup_expired)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_expired(self) -> None:
        with self._lock:
            now = time.time()
            expired = [k for k, ts in self._index.items() if now - ts >= self._TTL]
            for key in expired:
                self._evict(key)
                log.info(f"TTS cache expired: [dim]{key[:12]}...[/dim]")
        if self._index:
            self._schedule_cleanup()

    def _load_index(self) -> None:
        try:
            if not self._INDEX_FILE.exists():
                return
            data = json.loads(self._INDEX_FILE.read_text(encoding='utf-8'))
            now = time.time()
            self._index = {k: ts for k, ts in data.items() if now - ts < self._TTL}
            stale_files = set(self._CACHE_DIR.glob('*.wav')) - {
                self._CACHE_DIR / f"{k}.wav" for k in self._index
            }
            for f in stale_files:
                try:
                    f.unlink()
                except OSError:
                    pass
            if self._index:
                log.info(f"TTS cache: [cyan]{len(self._index)}[/cyan] cached audio(s)")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Failed to load TTS cache index: {e}")

    def _save_index(self) -> None:
        try:
            self._INDEX_FILE.write_text(
                json.dumps(self._index, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Failed to save TTS cache index: {e}")
