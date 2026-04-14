import json
from pathlib import Path
import sys
import threading
import time
from typing import (
    Dict,
    Optional,
)

from src import log

from src.audio_recorder import AudioRecorder
from src.clipboard_manager import ClipboardManager
from src.file_concatenator import (
    ConcatenatorSession,
    show_concatenator_dialog,
)
from src.history_window import HistoryWindow
from src.hotkey_handler import HotkeyHandler
from src.local_file_processor import LocalFileProcessor
from src.transcriber import Transcriber
from src.tray_icon import TrayIcon
from src.youtube_downloader import YouTubeDownloader


class VoicePasteApp:  # pylint: disable=too-many-instance-attributes
    def __init__(self, keep_model_loaded: bool = False, device_id: Optional[int] = None, gpu_profile: str = "standard"):
        self.audio_recorder = AudioRecorder(device_id=device_id)
        self.transcriber = Transcriber(keep_model_loaded=keep_model_loaded, gpu_profile=gpu_profile)
        self.clipboard_manager = ClipboardManager()
        self.youtube_downloader = YouTubeDownloader()
        self.local_file_processor = LocalFileProcessor()
        self.concat_session = ConcatenatorSession(
            on_complete=self._on_concat_complete,
            on_status=self._on_concat_status,
        )
        self.hotkey_handler = HotkeyHandler(
            voice_callback=self.on_voice_hotkey,
            youtube_callback=self.on_youtube_hotkey,
            file_callback=self.on_file_hotkey,
            concat_callback=self.on_concat_hotkey,
        )
        self.is_running = True
        self.processing_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.is_recording = False

        self.transcription_cache: Dict[str, Dict] = {}
        self.cache_ttl = 86400
        self.cache_file = Path.home() / '.voicepaste_cache.json'
        self.cache_cleanup_timer: Optional[threading.Timer] = None
        self._load_cache()

        self.history_window = HistoryWindow(
            get_history=self.get_history,
            copy_from_history=self.copy_from_history,
            delete_from_history=self.delete_from_history,
        )

        self.tray_icon = TrayIcon(
            on_quit=self.quit,
            on_toggle_recording=self.toggle_recording,
            on_toggle_keep_model=self.toggle_keep_model,
            get_model_status=self.get_model_status,
            on_transcribe_youtube=self.transcribe_youtube_from_dialog,
            on_transcribe_file=self.transcribe_file_from_dialog,
            on_set_gpu_profile=self.set_gpu_profile,
            get_gpu_profile=self.get_gpu_profile,
            on_show_history=self.show_history,
            on_file_concatenator=self.show_concatenator_dialog,
        )

    def start(self):
        log.startup_banner()

        device_info = self.audio_recorder.get_device_info()
        if device_info:
            log.audio_device(device_info['name'], self.audio_recorder.device_sample_rate)
        else:
            log.warn("No audio input device found - check microphone connection")

        log.info("Starting hotkey listener...")
        self.hotkey_handler.start()

        log.info("Starting system tray icon...")
        self.tray_icon.start()

        try:
            while not self.shutdown_event.is_set():
                self.shutdown_event.wait(timeout=0.5)
        except KeyboardInterrupt:
            log.info("Ctrl+C received - shutting down...")
            self.quit()

    def _try_use_cached_transcription(self, key: str) -> bool:
        if key not in self.transcription_cache:
            return False

        cached_entry = self.transcription_cache[key]
        if time.time() - cached_entry['timestamp'] < self.cache_ttl:
            log.info(f"Cache hit: [dim]{key[:80]}[/dim]")
            self.clipboard_manager.copy_to_clipboard(cached_entry['text'])
            log.clip("Cached transcription copied to clipboard")
            return True

        del self.transcription_cache[key]
        self._save_cache()
        return False

    def on_voice_hotkey(self, is_pressed: bool):
        if is_pressed:
            self._start_recording()
        else:
            self._stop_recording()

    def on_youtube_hotkey(self):
        def process_youtube():
            # pylint: disable=too-many-try-statements
            try:
                url = self.clipboard_manager.get_from_clipboard()
                if not url or not isinstance(url, str):
                    log.warn("Clipboard does not contain a URL")
                    return

                url = url.strip()
                if not self.youtube_downloader.is_youtube_url(url):
                    log.warn(f"Not a YouTube URL: [dim]{url[:80]}[/dim]")
                    return

                if self._try_use_cached_transcription(url):
                    return

                log.info(f"YouTube: [dim]{url}[/dim]")
                self.tray_icon.update_status("downloading")

                result = self.youtube_downloader.download_audio(url)
                if not result:
                    log.error("Audio download failed")
                    self.tray_icon.update_status("idle")
                    return

                audio_data, title = result
                log.info(f"Transcribing: [italic]{title}[/italic]")
                self.tray_icon.update_status("processing")

                text = self.transcriber.transcribe(audio_data)
                if text:
                    log.xscr(text)
                    self.clipboard_manager.copy_to_clipboard(text)
                    log.clip(f"Copied to clipboard ({len(text)} chars)")

                    self.transcription_cache[url] = {
                        'text': text,
                        'timestamp': time.time(),
                        'source_type': 'youtube',
                        'title': title,
                    }
                    self._save_cache()
                    self._schedule_cache_cleanup()
                else:
                    log.warn("No transcription result")

                self.tray_icon.update_status("idle")

            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(f"YouTube transcription error: {e}")
                self.tray_icon.update_status("idle")

        threading.Thread(target=process_youtube, daemon=True).start()

    def on_file_hotkey(self):  # pylint: disable=too-many-statements
        def process_files():
            # pylint: disable=too-many-try-statements,too-many-statements
            try:
                file_paths = self.clipboard_manager.get_file_paths_from_clipboard()
                if not file_paths:
                    log.warn("Clipboard does not contain a file path")
                    return

                valid_files = [fp for fp in file_paths if self.local_file_processor.is_valid_file_path(fp)]
                if not valid_files:
                    log.warn("No supported audio/video files in clipboard")
                    return

                total = len(valid_files)
                log.info(f"Found [cyan]{total}[/cyan] file(s) to process")

                all_transcriptions = []
                self.tray_icon.update_status("processing")

                for idx, file_path in enumerate(valid_files, 1):
                    cache_entry = self.transcription_cache.get(file_path)
                    if cache_entry and time.time() - cache_entry['timestamp'] < self.cache_ttl:
                        log.info(f"[{idx}/{total}] Cache hit: [dim]{Path(file_path).name}[/dim]")
                        all_transcriptions.append({
                            'filename': Path(file_path).name,
                            'text': cache_entry['text'],
                            'from_cache': True,
                        })
                        continue

                    log.info(f"[{idx}/{total}] Processing: [dim]{Path(file_path).name}[/dim]")

                    result = self.local_file_processor.process_file(file_path)
                    if not result:
                        log.error(f"Failed to process: {Path(file_path).name}")
                        continue

                    audio_data, filename = result
                    log.info(f"Transcribing: [italic]{filename}[/italic]")

                    text = self.transcriber.transcribe(audio_data)
                    if text:
                        log.xscr(text)

                        self.transcription_cache[file_path] = {
                            'text': text,
                            'timestamp': time.time(),
                            'source_type': 'file',
                            'title': filename,
                        }
                        self._save_cache()
                        self._schedule_cache_cleanup()

                        all_transcriptions.append({
                            'filename': filename,
                            'text': text,
                            'from_cache': False,
                        })
                    else:
                        log.warn(f"No transcription result for: {filename}")

                if all_transcriptions:
                    if len(all_transcriptions) == 1:
                        final_text = all_transcriptions[0]['text']
                    else:
                        parts = []
                        for trans in all_transcriptions:
                            parts.append(f"=== {trans['filename']} ===\n{trans['text']}")
                        final_text = "\n\n".join(parts)

                    self.clipboard_manager.copy_to_clipboard(final_text)
                    log.clip(f"{len(all_transcriptions)} transcription(s) copied to clipboard")
                else:
                    log.warn("No transcriptions to copy")

                self.tray_icon.update_status("idle")

            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(f"File transcription error: {e}")
                self.tray_icon.update_status("idle")

        threading.Thread(target=process_files, daemon=True).start()

    def on_concat_hotkey(self):
        clipboard_text = self.clipboard_manager.get_from_clipboard()
        if not clipboard_text:
            log.warn("Clipboard is empty")
            return

        text = clipboard_text.strip().strip('"').strip("'")
        if Path(text).is_dir():
            log.info(f"Folder detected - opening dialog: [dim]{text}[/dim]")
            self._open_concat_dialog(folder=text)
            return

        message = self.concat_session.process_clipboard(clipboard_text)
        log.info(message)

    def _on_concat_complete(self, result: str):
        self.clipboard_manager.copy_to_clipboard(result)

    def _on_concat_status(self, message: str):
        log.info(message)

    def _open_concat_dialog(self, folder: Optional[str] = None):
        def process():
            show_concatenator_dialog(initial_folder=folder)
        threading.Thread(target=process, daemon=True).start()

    def show_concatenator_dialog(self):
        self._open_concat_dialog()

    def _start_recording(self):
        with self.processing_lock:
            try:
                log.rec("Recording...")
                self.is_recording = True
                self.tray_icon.update_status("recording")
                self.audio_recorder.start_recording()
                self.transcriber.preload_for_recording()
            except RuntimeError as e:
                log.error(f"Recording start error: {e}")
                self.is_recording = False
                self.tray_icon.update_status("idle")
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(f"Unexpected error: {e}")
                self.is_recording = False
                self.tray_icon.update_status("idle")

    def _stop_recording(self):
        self.is_recording = False

        def process_audio():
            with self.processing_lock:
                log.rec("Recording stopped - processing...")
                self.tray_icon.update_status("processing")

                audio_data = self.audio_recorder.stop_recording()

                if audio_data is None:
                    log.warn("No audio data captured")
                    self.tray_icon.update_status("idle")
                    return

                duration = len(audio_data) / 16000

                if len(audio_data) < 1600:
                    log.warn(f"Recording too short ({duration:.2f}s) - ignoring")
                    self.tray_icon.update_status("idle")
                    return

                import numpy as np  # pylint: disable=import-outside-toplevel
                rms = np.sqrt(np.mean(audio_data**2))
                log.audio_info(f"{duration:.2f}s / {len(audio_data)} samples / RMS {rms:.4f}")

                try:
                    text = self.transcriber.transcribe(audio_data)
                    if text:
                        log.xscr(text)
                        self.clipboard_manager.copy_to_clipboard(text)
                        log.clip(f"Copied to clipboard ({len(text)} chars)")

                        cache_key = f"voice_{int(time.time() * 1000)}"
                        self.transcription_cache[cache_key] = {
                            'text': text,
                            'timestamp': time.time(),
                            'source_type': 'voice',
                            'title': f"Voice Recording ({duration:.1f}s)",
                        }
                        self._save_cache()
                        self._schedule_cache_cleanup()
                    else:
                        log.warn("Whisper returned no text")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.error(f"Transcription error: {e}")

                self.tray_icon.update_status("idle")

        threading.Thread(target=process_audio, daemon=True).start()

    def toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def toggle_keep_model(self):
        self.transcriber.keep_model_loaded = not self.transcriber.keep_model_loaded
        status = "enabled" if self.transcriber.keep_model_loaded else "disabled"
        log.model(f"Keep model loaded: {status}")

    def set_gpu_profile(self, profile: str):
        self.transcriber.set_gpu_profile(profile)

    def get_gpu_profile(self) -> str:
        return self.transcriber.gpu_profile

    def get_history(self):
        history = []
        for key, entry in self.transcription_cache.items():
            history.append({
                'key': key,
                'text': entry['text'],
                'timestamp': entry['timestamp'],
                'source_type': entry['source_type'],
                'title': entry['title'],
            })
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        return history

    def copy_from_history(self, key: str):
        if key in self.transcription_cache:
            text = self.transcription_cache[key]['text']
            self.clipboard_manager.copy_to_clipboard(text)
            log.clip(f"Copied from history: {self.transcription_cache[key]['title']}")
            return True
        return False

    def delete_from_history(self, key: str):
        if key in self.transcription_cache:
            title = self.transcription_cache[key]['title']
            del self.transcription_cache[key]
            self._save_cache()
            log.info(f"Deleted from history: {title}")
            return True
        return False

    def show_history(self):
        self.history_window.show()

    def get_model_status(self):
        if self.transcriber.model is None:
            return "Not loaded"
        if self.transcriber.current_device == "cuda":
            return "VRAM (GPU)"
        if self.transcriber.current_device == "cpu":
            return "RAM (CPU)"
        return "Unknown"

    def transcribe_youtube_from_dialog(self):
        def process():
            # pylint: disable=too-many-try-statements,import-outside-toplevel
            try:
                import customtkinter as ctk  # pylint: disable=import-outside-toplevel
                from src.dialog_utils import (  # pylint: disable=import-outside-toplevel
                    ACCENT, BG, DIM, ERROR, FG, SURFACE, setup_window,
                )

                win = ctk.CTk()
                setup_window(win, "VoicePaste - Transcribe YouTube", 540, 240)

                content = ctk.CTkFrame(win, fg_color=BG)
                content.pack(fill="both", expand=True, padx=24, pady=20)

                ctk.CTkLabel(content, text="Transcribe YouTube Video",
                             font=ctk.CTkFont(size=20, weight="bold"),
                             text_color=FG).pack(anchor="w")
                ctk.CTkLabel(content, text="Paste a YouTube URL and press Enter or Transcribe.",
                             font=ctk.CTkFont(size=12), text_color=DIM).pack(anchor="w", pady=(2, 12))

                clipboard = self.clipboard_manager.get_from_clipboard()
                initial_url = ""
                if clipboard and isinstance(clipboard, str) and self.youtube_downloader.is_youtube_url(clipboard.strip()):
                    initial_url = clipboard.strip()

                url_entry = ctk.CTkEntry(content, fg_color=SURFACE, border_color=SURFACE,
                                         text_color=FG, placeholder_text="https://www.youtube.com/watch?v=...",
                                         font=ctk.CTkFont(size=13), height=38)
                url_entry.pack(fill="x", pady=(0, 4))
                if initial_url:
                    url_entry.insert(0, initial_url)

                status_label = ctk.CTkLabel(content, text="", font=ctk.CTkFont(size=12),
                                             text_color=ERROR, anchor="w")
                status_label.pack(fill="x", pady=(0, 10))

                result = {'url': None}

                def on_ok() -> None:
                    url = url_entry.get().strip()
                    if not url:
                        status_label.configure(text="Paste a YouTube URL first.")
                        return
                    result['url'] = url
                    win.destroy()

                def on_cancel() -> None:
                    win.destroy()

                btn_row = ctk.CTkFrame(content, fg_color=BG)
                btn_row.pack(fill="x")
                ctk.CTkButton(btn_row, text="Cancel", command=on_cancel, width=100, height=38,
                              fg_color=SURFACE, text_color=FG, hover_color="#3a3a5c",
                              font=ctk.CTkFont(size=13)).pack(side="right")
                ctk.CTkButton(btn_row, text="Transcribe", command=on_ok, width=120, height=38,
                              fg_color=ACCENT, text_color=BG, hover_color="#a8c8ff",
                              font=ctk.CTkFont(size=13, weight="bold")).pack(side="right", padx=(0, 8))

                win.bind("<Return>", lambda _e: on_ok())
                win.bind("<Escape>", lambda _e: on_cancel())
                url_entry.focus()
                win.mainloop()

                if result['url']:
                    self.clipboard_manager.copy_to_clipboard(result['url'])
                    self.on_youtube_hotkey()
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(f"YouTube dialog error: {e}")

        threading.Thread(target=process, daemon=True).start()

    def transcribe_file_from_dialog(self):
        def process():
            # pylint: disable=too-many-try-statements,import-outside-toplevel
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()

                try:
                    root.iconbitmap(default='icon.ico')
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                filetypes = [
                    ("Audio/Video files", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma *.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                    ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma"),
                    ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                    ("All files", "*.*"),
                ]

                file_paths = filedialog.askopenfilenames(
                    title="Select Audio or Video File(s) - VoicePaste",
                    filetypes=filetypes,
                )
                root.destroy()

                if file_paths:
                    self.clipboard_manager.copy_to_clipboard('\n'.join(file_paths))
                    self.on_file_hotkey()
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(f"File dialog error: {e}")

        threading.Thread(target=process, daemon=True).start()

    def _load_cache(self):
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    current_time = time.time()
                    for key, value in data.items():
                        if isinstance(value, dict):
                            if current_time - value['timestamp'] < self.cache_ttl:
                                self.transcription_cache[key] = value
                        elif isinstance(value, (list, tuple)) and len(value) == 2:
                            text, timestamp = value
                            if current_time - timestamp < self.cache_ttl:
                                self.transcription_cache[key] = {
                                    'text': text,
                                    'timestamp': timestamp,
                                    'source_type': 'unknown',
                                    'title': 'Legacy Entry',
                                }
                    if self.transcription_cache:
                        log.info(f"Loaded [cyan]{len(self.transcription_cache)}[/cyan] cached transcription(s)")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.transcription_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"Failed to save cache: {e}")

    def _schedule_cache_cleanup(self):
        if self.cache_cleanup_timer:
            self.cache_cleanup_timer.cancel()

        self.cache_cleanup_timer = threading.Timer(self.cache_ttl, self._cleanup_cache)
        self.cache_cleanup_timer.daemon = True
        self.cache_cleanup_timer.start()

    def _cleanup_cache(self):
        current_time = time.time()
        keys_to_remove = []

        for key, entry in self.transcription_cache.items():
            if current_time - entry['timestamp'] >= self.cache_ttl:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.transcription_cache[key]
            log.info(f"Cache expired: [dim]{key[:80]}[/dim]")

        self._save_cache()

        if self.transcription_cache:
            self._schedule_cache_cleanup()

    def quit(self):
        log.info("Shutting down...")
        self.is_running = False
        if self.cache_cleanup_timer:
            self.cache_cleanup_timer.cancel()
        self._save_cache()
        self.hotkey_handler.stop()
        self.transcriber.shutdown()
        self.youtube_downloader.cleanup()
        self.local_file_processor.cleanup()
        self.tray_icon.stop()
        self.shutdown_event.set()
        sys.exit(0)
