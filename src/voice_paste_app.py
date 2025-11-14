import threading
import sys
import time
from typing import Optional, Dict, Tuple

from src.audio_recorder import AudioRecorder
from src.transcriber import Transcriber
from src.clipboard_manager import ClipboardManager
from src.hotkey_handler import HotkeyHandler
from src.tray_icon import TrayIcon
from src.youtube_downloader import YouTubeDownloader
from src.local_file_processor import LocalFileProcessor


class VoicePasteApp:
    def __init__(self, keep_model_loaded: bool = False, device_id: Optional[int] = None):
        self.audio_recorder = AudioRecorder(device_id=device_id)
        self.transcriber = Transcriber(keep_model_loaded=keep_model_loaded)
        self.clipboard_manager = ClipboardManager()
        self.youtube_downloader = YouTubeDownloader()
        self.local_file_processor = LocalFileProcessor()
        self.hotkey_handler = HotkeyHandler(
            voice_callback=self.on_voice_hotkey,
            youtube_callback=self.on_youtube_hotkey,
            file_callback=self.on_file_hotkey
        )
        self.is_running = True
        self.processing_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.is_recording = False

        self.transcription_cache: Dict[str, Tuple[str, float]] = {}
        self.cache_ttl = 3600
        self.cache_cleanup_timer: Optional[threading.Timer] = None

        self.tray_icon = TrayIcon(
            on_quit=self.quit,
            on_toggle_recording=self.toggle_recording,
            on_toggle_keep_model=self.toggle_keep_model,
            get_model_status=self.get_model_status,
            on_transcribe_youtube=self.transcribe_youtube_from_dialog,
            on_transcribe_file=self.transcribe_file_from_dialog
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

        cached_text, timestamp = self.transcription_cache[key]
        if time.time() - timestamp < self.cache_ttl:
            print(f"Using cached transcription for: {key}")
            self.clipboard_manager.copy_to_clipboard(cached_text)
            print("Cached transcription copied to clipboard!")
            return True

        del self.transcription_cache[key]
        return False

    def on_voice_hotkey(self, is_pressed: bool):
        if is_pressed:
            self._start_recording()
        else:
            self._stop_recording()

    def on_youtube_hotkey(self):
        def process_youtube():
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

                    self.transcription_cache[url] = (text, time.time())
                    self._schedule_cache_cleanup()
                else:
                    print("No transcription result")

                self.tray_icon.update_status("idle")

            except Exception as e:
                print(f"YouTube transcription error: {e}")
                self.tray_icon.update_status("idle")

        threading.Thread(target=process_youtube, daemon=True).start()

    def on_file_hotkey(self):
        def process_file():
            try:
                file_path = self.clipboard_manager.get_file_path_from_clipboard()
                if not file_path:
                    print("No file or file path in clipboard")
                    return

                if not self.local_file_processor.is_valid_file_path(file_path):
                    print(f"Not a valid audio/video file: {file_path}")
                    return

                if self._try_use_cached_transcription(file_path):
                    return

                print(f"Processing file: {file_path}")
                self.tray_icon.update_status("processing")

                result = self.local_file_processor.process_file(file_path)
                if not result:
                    print("Failed to process file")
                    self.tray_icon.update_status("idle")
                    return

                audio_data, filename = result
                print(f"Transcribing: {filename}")

                text = self.transcriber.transcribe(audio_data)
                if text:
                    print(f"Transcription ({len(text)} chars): {text[:100]}...")
                    self.clipboard_manager.copy_to_clipboard(text)
                    print("Transcription copied to clipboard!")

                    self.transcription_cache[file_path] = (text, time.time())
                    self._schedule_cache_cleanup()
                else:
                    print("No transcription result")

                self.tray_icon.update_status("idle")

            except Exception as e:
                print(f"File transcription error: {e}")
                self.tray_icon.update_status("idle")

        threading.Thread(target=process_file, daemon=True).start()

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
            except Exception as e:
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

                if audio_data is None or len(audio_data) < 1600:
                    print("Recording too short, ignoring...")
                    self.tray_icon.update_status("idle")
                    return

                try:
                    text = self.transcriber.transcribe(audio_data)
                    if text:
                        print(f"Transcription: {text}")
                        self.clipboard_manager.copy_to_clipboard(text)
                        print("Copied to clipboard!")
                    else:
                        print("No transcription result")
                except Exception as e:
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

    def get_model_status(self):
        if self.transcriber.model is None:
            return "Not loaded"
        elif self.transcriber.current_device == "cuda":
            return "VRAM (GPU)"
        elif self.transcriber.current_device == "cpu":
            return "RAM (CPU)"
        else:
            return "Unknown"

    def transcribe_youtube_from_dialog(self):
        def process():
            try:
                import tkinter as tk
                from tkinter import ttk

                dialog = tk.Tk()
                dialog.title("Transcribe YouTube Video")
                dialog.geometry("500x180")
                dialog.resizable(False, False)

                try:
                    dialog.iconbitmap(default='icon.ico')
                except Exception:
                    pass

                dialog.configure(bg='#f0f0f0')

                main_frame = ttk.Frame(dialog, padding="20")
                main_frame.pack(fill=tk.BOTH, expand=True)

                title_label = ttk.Label(
                    main_frame,
                    text="Enter YouTube URL",
                    font=('Segoe UI', 11, 'bold')
                )
                title_label.pack(pady=(0, 10))

                url_var = tk.StringVar()
                url_entry = ttk.Entry(
                    main_frame,
                    textvariable=url_var,
                    font=('Segoe UI', 10),
                    width=50
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
                    width=12
                )
                ok_button.pack(side=tk.LEFT, padx=5)

                cancel_button = ttk.Button(
                    button_frame,
                    text="Cancel",
                    command=on_cancel,
                    width=12
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
            except Exception as e:
                print(f"Error in YouTube dialog: {e}")

        threading.Thread(target=process, daemon=True).start()

    def transcribe_file_from_dialog(self):
        def process():
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()

                try:
                    root.iconbitmap(default='icon.ico')
                except Exception:
                    pass

                filetypes = [
                    ("Audio/Video files", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma *.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                    ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma"),
                    ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                    ("All files", "*.*")
                ]

                file_path = filedialog.askopenfilename(
                    title="Select Audio or Video File - VoicePaste",
                    filetypes=filetypes
                )
                root.destroy()

                if file_path:
                    self.clipboard_manager.copy_to_clipboard(file_path)
                    self.on_file_hotkey()
            except Exception as e:
                print(f"Error in file dialog: {e}")

        threading.Thread(target=process, daemon=True).start()

    def _schedule_cache_cleanup(self):
        if self.cache_cleanup_timer:
            self.cache_cleanup_timer.cancel()

        self.cache_cleanup_timer = threading.Timer(self.cache_ttl, self._cleanup_cache)
        self.cache_cleanup_timer.daemon = True
        self.cache_cleanup_timer.start()

    def _cleanup_cache(self):
        current_time = time.time()
        urls_to_remove = []

        for url, (_, timestamp) in self.transcription_cache.items():
            if current_time - timestamp >= self.cache_ttl:
                urls_to_remove.append(url)

        for url in urls_to_remove:
            del self.transcription_cache[url]
            print(f"Removed cached transcription for: {url}")

        if self.transcription_cache:
            self._schedule_cache_cleanup()

    def quit(self):
        print("Shutting down...")
        self.is_running = False
        if self.cache_cleanup_timer:
            self.cache_cleanup_timer.cancel()
        self.hotkey_handler.stop()
        self.transcriber.shutdown()
        self.youtube_downloader.cleanup()
        self.local_file_processor.cleanup()
        self.tray_icon.stop()
        self.shutdown_event.set()
        sys.exit(0)
