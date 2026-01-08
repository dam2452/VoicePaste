import argparse
from pathlib import Path
import sys

import pyaudio

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from src.voice_paste_app import VoicePasteApp  # pylint: disable=wrong-import-position


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
        help="Keep the Whisper model loaded in memory at all times (uses more GPU memory)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Audio input device ID (use --list-devices to see available devices)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )
    parser.add_argument(
        "--gpu-profile",
        type=str,
        choices=["standard", "high_end"],
        default="standard",
        help="GPU profile: 'standard' for RTX 2080S (8GB), 'high_end' for RTX 3090+ (24GB)",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        sys.exit(0)

    app = VoicePasteApp(
        keep_model_loaded=args.keep_model_loaded,
        device_id=args.device,
        gpu_profile=args.gpu_profile,
    )
    try:
        app.start()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
