import json
from pathlib import Path
import sys
import threading
import time
from typing import (
    Dict,
    Optional,
)

from src.audio_recorder import AudioRecorder
from src.clipboard_manager import ClipboardManager
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
        self.hotkey_handler = HotkeyHandler(
            voice_callback=self.on_voice_hotkey,
            youtube_callback=self.on_youtube_hotkey,
            file_callback=self.on_file_hotkey,
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
        )

    def start(self):
        print("VoicePaste started!")

        device_info = self.audio_recorder.get_device_info()
        if device_info:
            print(f"Using audio device: {device_info['name']}")
        else:
            print("Warning: No audio input device found!")
            print("Please check your microphone connection.")

        print("Press Shift+V to start/stop recording...")
        print("Press Shift+Y to transcribe YouTube video from clipboard...")
        print("Press Shift+F to transcribe audio/video file from clipboard...")
        print("Press Ctrl+C to quit")

        print("Starting hotkey listener...")
        self.hotkey_handler.start()

        print("Starting system tray icon...")
        self.tray_icon.start()

        try:
            while not self.shutdown_event.is_set():
                self.shutdown_event.wait(timeout=0.5)
        except KeyboardInterrupt:
            print("\nReceived Ctrl+C, shutting down...")
            self.quit()

    def _try_use_cached_transcription(self, key: str) -> bool:
        if key not in self.transcription_cache:
            return False

        cached_entry = self.transcription_cache[key]
        if time.time() - cached_entry['timestamp'] < self.cache_ttl:
            print(f"Using cached transcription for: {key}")
            self.clipboard_manager.copy_to_clipboard(cached_entry['text'])
            print("Cached transcription copied to clipboard!")
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
                    print("No URL in clipboard")
                    return

                url = url.strip()
                if not self.youtube_downloader.is_youtube_url(url):
                    print(f"Not a YouTube URL: {url}")
                    return

                if self._try_use_cached_transcription(url):
                    return

                print(f"Processing YouTube URL: {url}")
                self.tray_icon.update_status("downloading")

                result = self.youtube_downloader.download_audio(url)
                if not result:
                    print("Failed to download audio")
                    self.tray_icon.update_status("idle")
                    return

                audio_data, title = result
                print(f"Transcribing: {title}")
                self.tray_icon.update_status("processing")

                text = self.transcriber.transcribe(audio_data)
                if text:
                    print(f"Transcription ({len(text)} chars): {text[:100]}...")
                    self.clipboard_manager.copy_to_clipboard(text)
                    print("Transcription copied to clipboard!")

                    self.transcription_cache[url] = {
                        'text': text,
                        'timestamp': time.time(),
                        'source_type': 'youtube',
                        'title': title,
                    }
                    self._save_cache()
                    self._schedule_cache_cleanup()
                else:
                    print("No transcription result")

                self.tray_icon.update_status("idle")

            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"YouTube transcription error: {e}")
                self.tray_icon.update_status("idle")

        threading.Thread(target=process_youtube, daemon=True).start()

    def on_file_hotkey(self):  # pylint: disable=too-many-statements
        def process_files():
            # pylint: disable=too-many-try-statements,too-many-statements
            try:
                file_paths = self.clipboard_manager.get_file_paths_from_clipboard()
                if not file_paths:
                    print("No file or file path in clipboard")
                    return

                valid_files = [fp for fp in file_paths if self.local_file_processor.is_valid_file_path(fp)]
                if not valid_files:
                    print("No valid audio/video files in clipboard")
                    return

                print(f"Found {len(valid_files)} file(s) to process")
                sys.stdout.flush()

                all_transcriptions = []
                self.tray_icon.update_status("processing")

                for idx, file_path in enumerate(valid_files, 1):
                    cache_entry = self.transcription_cache.get(file_path)
                    if cache_entry and time.time() - cache_entry['timestamp'] < self.cache_ttl:
                        print(f"[{idx}/{len(valid_files)}] Using cached transcription for: {Path(file_path).name}")
                        sys.stdout.flush()
                        all_transcriptions.append({
                            'filename': Path(file_path).name,
                            'text': cache_entry['text'],
                            'from_cache': True,
                        })
                        continue

                    print(f"[{idx}/{len(valid_files)}] Processing file: {file_path}")
                    sys.stdout.flush()

                    result = self.local_file_processor.process_file(file_path)
                    if not result:
                        print(f"Failed to process file: {file_path}")
                        sys.stdout.flush()
                        continue

                    audio_data, filename = result
                    print(f"Transcribing: {filename}")
                    sys.stdout.flush()

                    text = self.transcriber.transcribe(audio_data)
                    if text:
                        print(f"Transcription ({len(text)} chars): {text[:100]}...")
                        sys.stdout.flush()

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
                        print(f"No transcription result for: {filename}")
                        sys.stdout.flush()

                if all_transcriptions:
                    if len(all_transcriptions) == 1:
                        final_text = all_transcriptions[0]['text']
                    else:
                        parts = []
                        for trans in all_transcriptions:
                            parts.append(f"=== {trans['filename']} ===\n{trans['text']}")
                        final_text = "\n\n".join(parts)

                    self.clipboard_manager.copy_to_clipboard(final_text)
                    print(f"\n{len(all_transcriptions)} transcription(s) copied to clipboard!")
                    sys.stdout.flush()
                else:
                    print("No transcriptions to copy")
                    sys.stdout.flush()

                self.tray_icon.update_status("idle")

            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"File transcription error: {e}")
                self.tray_icon.update_status("idle")

        threading.Thread(target=process_files, daemon=True).start()

    def _start_recording(self):
        with self.processing_lock:
            try:
                print("Started recording...")
                self.is_recording = True
                self.tray_icon.update_status("recording")
                self.audio_recorder.start_recording()
                self.transcriber.preload_for_recording()
            except RuntimeError as e:
                print(f"Error starting recording: {e}")
                self.is_recording = False
                self.tray_icon.update_status("idle")
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Unexpected error: {e}")
                self.is_recording = False
                self.tray_icon.update_status("idle")

    def _stop_recording(self):
        self.is_recording = False

        def process_audio():
            with self.processing_lock:
                print("Stopped recording. Processing...")
                self.tray_icon.update_status("processing")

                audio_data = self.audio_recorder.stop_recording()

                if audio_data is None:
                    print("No audio data captured!")
                    self.tray_icon.update_status("idle")
                    return

                duration = len(audio_data) / 16000
                print(f"Recorded {duration:.2f}s of audio, {len(audio_data)} samples")

                if len(audio_data) < 1600:
                    print("Recording too short, ignoring...")
                    self.tray_icon.update_status("idle")
                    return

                import numpy as np  # pylint: disable=import-outside-toplevel
                rms = np.sqrt(np.mean(audio_data**2))
                print(f"Audio RMS level: {rms:.6f}")

                try:
                    text = self.transcriber.transcribe(audio_data)
                    if text:
                        print(f"Transcription: {text}")
                        self.clipboard_manager.copy_to_clipboard(text)
                        print("Copied to clipboard!")

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
                        print("No transcription result (empty text from Whisper)")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"Transcription error: {e}")

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
        print(f"Keep model loaded: {status}")

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
            print(f"Copied from history: {self.transcription_cache[key]['title']}")
            return True
        return False

    def delete_from_history(self, key: str):
        if key in self.transcription_cache:
            title = self.transcription_cache[key]['title']
            del self.transcription_cache[key]
            self._save_cache()
            print(f"Deleted from history: {title}")
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
                import tkinter as tk
                from tkinter import ttk

                dialog = tk.Tk()
                dialog.title("Transcribe YouTube Video")
                dialog.geometry("500x180")
                dialog.resizable(False, False)

                try:
                    dialog.iconbitmap(default='icon.ico')
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                dialog.configure(bg='#f0f0f0')

                main_frame = ttk.Frame(dialog, padding="20")
                main_frame.pack(fill=tk.BOTH, expand=True)

                title_label = ttk.Label(
                    main_frame,
                    text="Enter YouTube URL",
                    font=('Segoe UI', 11, 'bold'),
                )
                title_label.pack(pady=(0, 10))

                url_var = tk.StringVar()
                url_entry = ttk.Entry(
                    main_frame,
                    textvariable=url_var,
                    font=('Segoe UI', 10),
                    width=50,
                )
                url_entry.pack(pady=10, ipady=5)
                url_entry.focus()

                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=15)

                result = {'url': None}

                def on_ok():
                    result['url'] = url_var.get().strip()
                    dialog.destroy()

                def on_cancel():
                    dialog.destroy()

                ok_button = ttk.Button(
                    button_frame,
                    text="Transcribe",
                    command=on_ok,
                    width=12,
                )
                ok_button.pack(side=tk.LEFT, padx=5)

                cancel_button = ttk.Button(
                    button_frame,
                    text="Cancel",
                    command=on_cancel,
                    width=12,
                )
                cancel_button.pack(side=tk.LEFT, padx=5)

                url_entry.bind('<Return>', lambda e: on_ok())
                url_entry.bind('<Escape>', lambda e: on_cancel())

                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
                y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
                dialog.geometry(f'+{x}+{y}')

                dialog.mainloop()

                if result['url']:
                    self.clipboard_manager.copy_to_clipboard(result['url'])
                    self.on_youtube_hotkey()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error in YouTube dialog: {e}")

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
                print(f"Error in file dialog: {e}")

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
                        print(f"Loaded {len(self.transcription_cache)} cached transcription(s)")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to load cache: {e}")

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.transcription_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to save cache: {e}")

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
            print(f"Removed cached transcription for: {key}")

        self._save_cache()

        if self.transcription_cache:
            self._schedule_cache_cleanup()

    def quit(self):
        print("Shutting down...")
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
