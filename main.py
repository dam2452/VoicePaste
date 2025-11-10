import sys
import os
import argparse
import pyaudio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.voice_paste_app import VoicePasteApp


def list_devices():
    print("Available audio input devices:")
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"  {i}: {info['name']} (channels: {info['maxInputChannels']})")
    p.terminate()


def main():
    parser = argparse.ArgumentParser(description="VoicePaste - Voice to text with clipboard")
    parser.add_argument(
        "--keep-model-loaded",
        action="store_true",
        help="Keep the Whisper model loaded in memory at all times (uses more GPU memory)"
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Audio input device ID (use --list-devices to see available devices)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit"
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        sys.exit(0)

    app = VoicePasteApp(keep_model_loaded=args.keep_model_loaded, device_id=args.device)
    try:
        app.start()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
