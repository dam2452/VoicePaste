import threading
import sys
from typing import Optional
import numpy as np

from src.audio_recorder import AudioRecorder
from src.transcriber import Transcriber
from src.clipboard_manager import ClipboardManager
from src.hotkey_handler import HotkeyHandler
from src.tray_icon import TrayIcon


class VoicePasteApp:
    def __init__(self, keep_model_loaded: bool = False, device_id: Optional[int] = None):
        self.audio_recorder = AudioRecorder(device_id=device_id)
        self.transcriber = Transcriber(keep_model_loaded=keep_model_loaded)
        self.clipboard_manager = ClipboardManager()
        self.tray_icon = TrayIcon(on_quit=self.quit)
        self.hotkey_handler = HotkeyHandler(callback=self.on_hotkey)
        self.is_running = True
        self.processing_lock = threading.Lock()
        self.shutdown_event = threading.Event()

    def start(self):
        print("VoicePaste started!")

        device_info = self.audio_recorder.get_device_info()
        if device_info:
            print(f"Using audio device: {device_info['name']}")
        else:
            print("Warning: No audio input device found!")
            print("Please check your microphone connection.")

        print("Press Shift+V to start recording...")

        print("Starting hotkey listener...")
        self.hotkey_handler.start()

        print("Starting system tray icon...")
        self.tray_icon.start()

        try:
            self.shutdown_event.wait()
        except KeyboardInterrupt:
            print("\nReceived Ctrl+C, shutting down...")
            self.quit()

    def on_hotkey(self, is_pressed: bool):
        if is_pressed:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        with self.processing_lock:
            try:
                print("Started recording...")
                self.tray_icon.update_status("recording")
                self.audio_recorder.start_recording()
                self.transcriber.preload_for_recording()
            except RuntimeError as e:
                print(f"Error starting recording: {e}")
                self.tray_icon.update_status("idle")
            except Exception as e:
                print(f"Unexpected error: {e}")
                self.tray_icon.update_status("idle")

    def _stop_recording(self):
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

    def quit(self):
        print("Shutting down...")
        self.is_running = False
        self.hotkey_handler.stop()
        self.transcriber.shutdown()
        self.tray_icon.stop()
        self.shutdown_event.set()
        sys.exit(0)
