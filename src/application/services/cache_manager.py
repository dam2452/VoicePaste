import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from src.core.dtos import CacheEntry
from src import log


class TranscriptionCacheManager:
    _TTL = 86400
    _CACHE_FILE = Path.home() / '.voicepaste_cache.json'

    def __init__(self) -> None:
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._cleanup_timer: Optional[threading.Timer] = None
        self._load()

    def get(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() - entry.timestamp >= self._TTL:
                del self._cache[key]
                self._save()
                return None
            log.info(f"Cache hit: [dim]{key[:80]}[/dim]")
            return entry

    def put(self, key: str, entry: CacheEntry) -> None:
        with self._lock:
            self._cache[key] = entry
            self._save()
        self._schedule_cleanup()

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._cache:
                return False
            title = self._cache[key].title
            del self._cache[key]
            self._save()
        log.info(f"Deleted from history: {title}")
        return True

    def get_all(self) -> Dict[str, CacheEntry]:
        with self._lock:
            return dict(self._cache)

    def shutdown(self) -> None:
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        with self._lock:
            self._save()

    def _schedule_cleanup(self) -> None:
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
        self._cleanup_timer = threading.Timer(self._TTL, self._cleanup_expired)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_expired(self) -> None:
        with self._lock:
            current_time = time.time()
            keys_to_remove = [k for k, e in self._cache.items() if current_time - e.timestamp >= self._TTL]
            for key in keys_to_remove:
                del self._cache[key]
                log.info(f"Cache expired: [dim]{key[:80]}[/dim]")
            if keys_to_remove:
                self._save()
        if self._cache:
            self._schedule_cleanup()

    def _load(self) -> None:
        try:
            if not self._CACHE_FILE.exists():
                return
            with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            current_time = time.time()
            for key, value in data.items():
                if isinstance(value, dict) and current_time - value.get('timestamp', 0) < self._TTL:
                    self._cache[key] = CacheEntry(
                        text=value['text'],
                        timestamp=value['timestamp'],
                        source_type=value.get('source_type', 'unknown'),
                        title=value.get('title', 'Unknown'),
                    )
                elif isinstance(value, (list, tuple)) and len(value) == 2:
                    text, timestamp = value
                    if current_time - timestamp < self._TTL:
                        self._cache[key] = CacheEntry(
                            text=text, timestamp=timestamp,
                            source_type='unknown', title='Legacy Entry',
                        )
            if self._cache:
                log.info(f"Loaded [cyan]{len(self._cache)}[/cyan] cached transcription(s)")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Failed to load cache: {e}")

    def _save(self) -> None:
        try:
            data = {
                key: {
                    'text': e.text,
                    'timestamp': e.timestamp,
                    'source_type': e.source_type,
                    'title': e.title,
                }
                for key, e in self._cache.items()
            }
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Failed to save cache: {e}")
