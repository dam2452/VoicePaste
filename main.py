import argparse
from pathlib import Path
import sys
import threading
from typing import (
    Dict,
    List,
    Optional,
)

import pyaudio

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from src import log
from src.application.services.cache_manager import TranscriptionCacheManager
from src.application.services.tts_audio_cache import TTSAudioCache
from src.application.use_cases.concatenate_files import ConcatenateFilesUseCase
from src.application.use_cases.process_tts import ProcessTTSUseCase
from src.application.use_cases.record_voice import RecordVoiceUseCase
from src.application.use_cases.summarize_clipboard import SummarizeClipboardUseCase
from src.application.use_cases.transcribe_file import TranscribeFileUseCase
from src.application.use_cases.transcribe_youtube import TranscribeYouTubeUseCase
from src.core.dtos import CacheEntry
from src.env_config import (
    get as env_get,
    load_env,
)
from src.infrastructure.ai.faster_whisper_transcriber import FasterWhisperTranscriber
from src.infrastructure.ai.summarizer import (
    GeminiSummarizerBackend,
    OpenAICompatibleSummarizerBackend,
    Summarizer,
)
from src.infrastructure.ai.tts_engine import (
    EdgeTTSBackend,
    GeminiTTSBackend,
    OmniVoiceBackend,
    OpenAICompatibleBackend,
    TTSEngine,
)
from src.infrastructure.system.audio_recorder import AudioRecorder
from src.infrastructure.system.local_file_processor import LocalFileProcessor
from src.infrastructure.system.os_clipboard import OsClipboard
from src.infrastructure.system.yt_dlp_downloader import YtDlpDownloader
from src.infrastructure.ui.dialogs import (
    show_file_dialog,
    show_youtube_dialog,
)
from src.infrastructure.ui.file_concatenator import (
    ConcatenatorSession,
    show_concatenator_dialog,
)
from src.infrastructure.ui.history_window import HistoryWindow
from src.infrastructure.ui.hotkey_manager import HotkeyManager
from src.infrastructure.ui.tray_icon import TrayIcon


def _build_tts_backend():
    backend = env_get("TTS_BACKEND", "omnivoice")
    if backend == "gemini":
        api_key = env_get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("TTS_BACKEND=gemini requires GEMINI_API_KEY to be set.")
        return GeminiTTSBackend(
            api_key=api_key,
            voice=env_get("TTS_GEMINI_VOICE", "Kore"),
            model=env_get("TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        )
    if backend == "edge_tts":
        return EdgeTTSBackend(voice=env_get("TTS_VOICE", "en-US-AriaNeural"))
    if backend == "openai":
        return OpenAICompatibleBackend(
            api_url=env_get("TTS_API_URL", "http://localhost:5959/v1"),
            api_key=env_get("TTS_API_KEY", ""),
            model=env_get("TTS_MODEL", "omnivoice"),
            voice=env_get("TTS_VOICE", "auto"),
        )
    speed_raw = env_get("TTS_SPEED", "")
    return OmniVoiceBackend(
        api_url=env_get("TTS_API_URL", "http://localhost:5959"),
        voice=env_get("TTS_VOICE", "a969b458"),
        num_step=int(env_get("TTS_NUM_STEP", "32")),
        speed=float(speed_raw) if speed_raw else None,
    )


def _build_summarizer_backend():
    backend = env_get("SUMM_BACKEND", "openai")
    if backend == "gemini":
        api_key = env_get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("SUMM_BACKEND=gemini requires GEMINI_API_KEY to be set.")
        return GeminiSummarizerBackend(
            api_key=api_key,
            model=env_get("SUMM_MODEL", "gemini-3-flash-preview"),
        )
    return OpenAICompatibleSummarizerBackend(
        api_url=env_get("SUMM_API_URL", "http://localhost:1234/v1"),
        api_key=env_get("SUMM_API_KEY", ""),
        model=env_get("SUMM_MODEL", "google/gemma-4-26b-a4b"),
    )


def _load_prompt(filename: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def _cache_to_history(cache: TranscriptionCacheManager) -> List[Dict]:
    return sorted(
        [
            {
                'key': k, 'text': v.text, 'timestamp': v.timestamp,
                'source_type': v.source_type, 'title': v.title,
            }
            for k, v in cache.get_all().items()
        ],
        key=lambda x: x['timestamp'],
        reverse=True,
    )


def list_devices() -> None:
    from rich.table import Table  # pylint: disable=import-outside-toplevel
    p = pyaudio.PyAudio()
    table = Table(title="Dostepne urzadzenia wejsciowe audio", border_style="cyan")
    table.add_column("ID", style="bold cyan", justify="right")
    table.add_column("Nazwa", style="white")
    table.add_column("Kanaly", style="dim", justify="right")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            table.add_row(str(i), info['name'], str(info['maxInputChannels']))
    p.terminate()
    log.console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="AIToys - Voice to text with clipboard")
    parser.add_argument("--keep-model-loaded", action="store_true")
    parser.add_argument("--device", type=int)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--gpu-profile", type=str, choices=["standard", "high_end"], default="standard")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        sys.exit(0)

    load_env()

    clipboard = OsClipboard()
    cache = TranscriptionCacheManager()

    recorder = AudioRecorder(device_id=args.device)
    transcriber = FasterWhisperTranscriber(
        keep_model_loaded=args.keep_model_loaded,
        gpu_profile=args.gpu_profile,
    )
    yt_downloader = YtDlpDownloader()
    file_processor = LocalFileProcessor()

    tts_engine = TTSEngine()
    tts_engine.set_backend(_build_tts_backend())
    tts_audio_cache = TTSAudioCache()

    summarizer = Summarizer()
    summarizer.set_backend(_build_summarizer_backend())
    base_prompt = _load_prompt("summarize.txt")
    if base_prompt:
        summarizer.set_system_prompt(base_prompt)
    tts_extra = _load_prompt("summarize_tts.txt")
    tts_summarize_prompt = f"{base_prompt}\n\n{tts_extra}" if tts_extra else base_prompt
    pre_summarize = env_get("TTS_PRE_SUMMARIZE", "false").lower() == "true"

    concat_session = ConcatenatorSession(
        on_complete=clipboard.write_text,
        on_status=log.info,
    )

    shutdown_event = threading.Event()

    def on_quit() -> None:
        log.info("Shutting down...")
        cache.shutdown()
        tts_audio_cache.shutdown()
        hotkeys.stop()
        tts_engine.shutdown()
        transcriber.shutdown()
        yt_downloader.cleanup()
        file_processor.cleanup()
        tray.stop()
        shutdown_event.set()
        sys.exit(0)

    tray = TrayIcon(
        on_quit=on_quit,
        on_toggle_recording=None,
        on_toggle_keep_model=lambda: _toggle_keep_model(transcriber, tray),
        get_model_status=transcriber.get_model_status,
        on_transcribe_youtube=lambda: show_youtube_dialog(
            on_url=lambda url: (clipboard.write_text(url), threading.Thread(target=record_yt_uc.execute, daemon=True).start()),
            is_youtube_url=yt_downloader.is_valid_url,
            initial_clipboard=clipboard.read_text(),
        ),
        on_transcribe_file=lambda: show_file_dialog(
            on_paths=lambda paths: (clipboard.write_text(paths), threading.Thread(target=file_uc.execute, daemon=True).start()),
        ),
        on_set_gpu_profile=transcriber.set_gpu_profile,
        get_gpu_profile=lambda: transcriber.gpu_profile,
        on_show_history=lambda: history_window.show(),  # pylint: disable=unnecessary-lambda
        on_file_concatenator=lambda: threading.Thread(target=show_concatenator_dialog, daemon=True).start(),
        on_tts=lambda: threading.Thread(target=tts_uc.toggle, daemon=True).start(),
        on_tts_summarize=lambda: threading.Thread(target=tts_summarize_uc.toggle, daemon=True).start(),
        on_summarize=lambda: threading.Thread(target=summarize_uc.execute, daemon=True).start(),
    )

    voice_uc = RecordVoiceUseCase(
        recorder=recorder, transcriber=transcriber,
        clipboard=clipboard, cache=cache, notifier=tray,
    )
    tray.on_toggle_recording = voice_uc.toggle

    record_yt_uc = TranscribeYouTubeUseCase(
        clipboard=clipboard, downloader=yt_downloader,
        transcriber=transcriber, cache=cache, notifier=tray,
    )
    file_uc = TranscribeFileUseCase(
        clipboard=clipboard, processor=file_processor,
        transcriber=transcriber, cache=cache, notifier=tray,
    )
    tts_uc = ProcessTTSUseCase(
        clipboard=clipboard, tts=tts_engine, notifier=tray,
        summarizer=summarizer, tts_system_prompt=tts_summarize_prompt,
        pre_summarize=pre_summarize, audio_cache=tts_audio_cache,
    )
    tts_summarize_uc = ProcessTTSUseCase(
        clipboard=clipboard, tts=tts_engine, notifier=tray,
        summarizer=summarizer, tts_system_prompt=tts_summarize_prompt,
        pre_summarize=True, audio_cache=tts_audio_cache,
    )
    summarize_uc = SummarizeClipboardUseCase(
        clipboard=clipboard, summarizer=summarizer, notifier=tray,
    )
    concat_uc = ConcatenateFilesUseCase(
        clipboard=clipboard,
        concat_session=concat_session,
        open_dialog=lambda folder: show_concatenator_dialog(initial_folder=folder),
    )

    history_window = HistoryWindow(
        get_history=lambda: _cache_to_history(cache),
        copy_from_history=lambda key: _copy_from_cache(key, cache, clipboard),
        delete_from_history=cache.delete,
    )

    hotkeys = HotkeyManager()
    hotkeys.bind_shift('v', voice_uc.toggle)
    hotkeys.bind_shift('y', lambda: threading.Thread(target=record_yt_uc.execute, daemon=True).start())
    hotkeys.bind_shift('f', lambda: threading.Thread(target=file_uc.execute, daemon=True).start())
    hotkeys.bind_shift('k', lambda: threading.Thread(target=concat_uc.execute, daemon=True).start())
    hotkeys.bind_shift('l', lambda: threading.Thread(target=tts_uc.toggle, daemon=True).start())
    hotkeys.bind_shift('r', lambda: threading.Thread(target=tts_summarize_uc.toggle, daemon=True).start())
    hotkeys.bind_shift('s', lambda: threading.Thread(target=summarize_uc.execute, daemon=True).start())

    log.startup_banner()

    device_info = recorder.get_device_info()
    if device_info:
        log.audio_device(device_info['name'], recorder.device_sample_rate)
    else:
        log.warn("No audio input device found - check microphone connection")

    log.info("Starting hotkey listener...")
    hotkeys.start()
    log.info("Starting system tray icon...")
    tray.start()

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=0.5)
    except KeyboardInterrupt:
        log.info("Ctrl+C received - shutting down...")
        on_quit()


def _toggle_keep_model(transcriber: FasterWhisperTranscriber, tray: TrayIcon) -> None:
    transcriber.keep_model_loaded = not transcriber.keep_model_loaded
    status = "enabled" if transcriber.keep_model_loaded else "disabled"
    log.model(f"Keep model loaded: {status}")
    tray.keep_model_enabled = transcriber.keep_model_loaded


def _copy_from_cache(key: str, cache: TranscriptionCacheManager, clipboard: OsClipboard) -> bool:
    entry: Optional[CacheEntry] = cache.get_all().get(key)
    if entry:
        clipboard.write_text(entry.text)
        log.clip(f"Copied from history: {entry.title}")
        return True
    return False


if __name__ == "__main__":
    main()
