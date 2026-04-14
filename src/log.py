import sys
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if sys.platform == "win32":
    import io
    _utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
else:
    _utf8_stdout = sys.stdout

console = Console(highlight=False, force_terminal=True, legacy_windows=False, file=_utf8_stdout)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _line(tag: str, tag_color: str, msg: str) -> None:
    console.print(f"[dim]{_ts()}[/dim]  [{tag_color} bold]{tag:<5}[/{tag_color} bold]  {msg}")


def info(msg: str) -> None:
    _line("INFO", "cyan", msg)


def ok(msg: str) -> None:
    _line("OK", "green", f"[green]{msg}[/green]")


def warn(msg: str) -> None:
    _line("WARN", "yellow", f"[yellow]{msg}[/yellow]")


def error(msg: str) -> None:
    _line("ERR", "red", f"[red]{msg}[/red]")


def rec(msg: str) -> None:
    _line("REC", "magenta", f"[magenta]{msg}[/magenta]")


def model(msg: str) -> None:
    _line("MODEL", "blue", f"[blue]{msg}[/blue]")


def clip(msg: str) -> None:
    _line("CLIP", "green", f"[bold green]{msg}[/bold green]")


def xscr(text: str, chars: int | None = None) -> None:
    preview = text[:120].replace("\n", " ")
    suffix = "..." if len(text) > 120 else ""
    char_info = f" [dim]({chars or len(text)} chars)[/dim]" if (chars or text) else ""
    _line("XSCR", "bright_green", f"[bright_green]{preview}{suffix}[/bright_green]{char_info}")


def segment(idx: int, text: str, confidence: float) -> None:
    bar = _conf_bar(confidence)
    _line("SEG", "dim", f"[dim]{idx}[/dim]  {bar}  [italic]{text.strip()}[/italic]")


def _conf_bar(logprob: float) -> str:
    clamped = max(0.0, min(1.0, (logprob + 1.0)))
    filled = round(clamped * 5)
    color = "green" if clamped > 0.6 else ("yellow" if clamped > 0.3 else "red")
    empty = 5 - filled
    return f"[{color}]{'#' * filled}{'.' * empty}[/{color}]"


def startup_banner() -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="white")

    bindings = [
        ("Shift+V", "Start / stop voice recording"),
        ("Shift+Y", "Transcribe YouTube URL from clipboard"),
        ("Shift+F", "Transcribe audio/video file from clipboard"),
        ("Shift+K", "Concatenate files"),
        ("Ctrl+C", "Quit"),
    ]
    for key, desc in bindings:
        table.add_row(key, desc)

    panel = Panel(
        table,
        title="[bold white]VoicePaste[/bold white]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def audio_device(name: str, sample_rate: int) -> None:
    _line("MIC", "cyan", f"[cyan]{name}[/cyan]  [dim]{sample_rate} Hz[/dim]")


def audio_info(msg: str) -> None:
    _line("AUD", "cyan", f"[dim]{msg}[/dim]")
