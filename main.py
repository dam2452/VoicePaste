import argparse
from pathlib import Path
import sys

import pyaudio

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from src.log import console  # pylint: disable=wrong-import-position
from src.voice_paste_app import VoicePasteApp  # pylint: disable=wrong-import-position


def list_devices():
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
    console.print(table)


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
        from src.log import error  # pylint: disable=import-outside-toplevel
        error(f"Krytyczny blad: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
