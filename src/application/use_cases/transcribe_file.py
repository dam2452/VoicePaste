import time
from pathlib import Path
from typing import List

from src.core.dtos import CacheEntry
from src.core.interfaces import ICacheManager, IAppNotifier, IClipboard, ITranscriber, ILocalFileProcessor
from src import log


class TranscribeFileUseCase:
    def __init__(
        self,
        clipboard: IClipboard,
        processor: ILocalFileProcessor,
        transcriber: ITranscriber,
        cache: ICacheManager,
        notifier: IAppNotifier,
    ) -> None:
        self._clipboard = clipboard
        self._processor = processor
        self._transcriber = transcriber
        self._cache = cache
        self._notifier = notifier

    def execute(self) -> None:
        # pylint: disable=too-many-try-statements
        try:
            file_paths = self._clipboard.read_file_paths()
            if not file_paths:
                log.warn("Clipboard does not contain a file path")
                return

            valid = [fp for fp in file_paths if self._processor.is_valid_path(fp)]
            if not valid:
                log.warn("No supported audio/video files in clipboard")
                return

            total = len(valid)
            log.info(f"Found [cyan]{total}[/cyan] file(s) to process")
            self._notifier.update_status("processing")

            results = self._process_all(valid)

            if results:
                final_text = results[0] if len(results) == 1 else self._merge(results)
                self._clipboard.write_text(final_text)
                log.clip(f"{len(results)} transcription(s) copied to clipboard")
            else:
                log.warn("No transcriptions to copy")

            self._notifier.update_status("idle")

        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"File transcription error: {e}")
            self._notifier.update_status("idle")

    def _process_all(self, file_paths: List[str]) -> List[str]:
        results = []
        total = len(file_paths)
        for idx, file_path in enumerate(file_paths, 1):
            cached = self._cache.get(file_path)
            if cached:
                log.info(f"[{idx}/{total}] Cache hit: [dim]{Path(file_path).name}[/dim]")
                results.append(cached.text)
                continue

            log.info(f"[{idx}/{total}] Processing: [dim]{Path(file_path).name}[/dim]")
            audio = self._processor.process(file_path)
            if not audio:
                log.error(f"Failed to process: {Path(file_path).name}")
                continue

            log.info(f"Transcribing: [italic]{audio.source_name}[/italic]")
            text = self._transcriber.transcribe(audio)
            if text:
                log.xscr(text)
                self._cache.put(file_path, CacheEntry(
                    text=text, timestamp=time.time(),
                    source_type='file', title=audio.source_name,
                ))
                results.append(text)
            else:
                log.warn(f"No transcription result for: {audio.source_name}")

        return results

    @staticmethod
    def _merge(transcriptions: List[str]) -> str:
        return "\n\n".join(transcriptions)
