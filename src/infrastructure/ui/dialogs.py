import threading
import tkinter as tk
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from src.infrastructure.ui.dialog_utils import ACCENT, BG, DIM, ERROR, FG, SURFACE, setup_window
from src import log


def show_youtube_dialog(
    on_url: Callable[[str], None],
    is_youtube_url: Callable[[str], bool],
    initial_clipboard: str = "",
) -> None:
    def _run() -> None:
        try:
            _run_youtube_dialog(on_url, is_youtube_url, initial_clipboard)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"YouTube dialog error: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _run_youtube_dialog(
    on_url: Callable[[str], None],
    is_youtube_url: Callable[[str], bool],
    initial_clipboard: str,
) -> None:
    win = ctk.CTk()
    setup_window(win, "AIToys - Transcribe YouTube", 540, 240)

    content = ctk.CTkFrame(win, fg_color=BG)
    content.pack(fill="both", expand=True, padx=24, pady=20)

    ctk.CTkLabel(
        content, text="Transcribe YouTube Video",
        font=ctk.CTkFont(size=20, weight="bold"), text_color=FG,
    ).pack(anchor="w")
    ctk.CTkLabel(
        content, text="Paste a YouTube URL and press Enter or Transcribe.",
        font=ctk.CTkFont(size=12), text_color=DIM,
    ).pack(anchor="w", pady=(2, 12))

    initial_url = ""
    stripped = initial_clipboard.strip()
    if stripped and is_youtube_url(stripped):
        initial_url = stripped

    url_entry = ctk.CTkEntry(
        content, fg_color=SURFACE, border_color=SURFACE,
        text_color=FG, placeholder_text="https://www.youtube.com/watch?v=...",
        font=ctk.CTkFont(size=13), height=38,
    )
    url_entry.pack(fill="x", pady=(0, 4))
    if initial_url:
        url_entry.insert(0, initial_url)

    status_label = ctk.CTkLabel(
        content, text="", font=ctk.CTkFont(size=12), text_color=ERROR, anchor="w",
    )
    status_label.pack(fill="x", pady=(0, 10))

    result: dict = {'url': None}

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
    ctk.CTkButton(
        btn_row, text="Cancel", command=on_cancel, width=110, height=44,
        fg_color=SURFACE, text_color=FG, hover_color="#3a3a5c", font=ctk.CTkFont(size=13),
    ).pack(side="right")
    ctk.CTkButton(
        btn_row, text="Transcribe", command=on_ok, width=130, height=44,
        fg_color=ACCENT, text_color=BG, hover_color="#a8c8ff",
        font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(side="right", padx=(0, 8))

    win.bind("<Return>", lambda _: on_ok())
    win.bind("<Escape>", lambda _: on_cancel())
    url_entry.focus()
    win.mainloop()

    if result['url']:
        on_url(result['url'])


def show_file_dialog(on_paths: Callable[[str], None]) -> None:
    def _run() -> None:
        try:
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
            paths = filedialog.askopenfilenames(
                title="Select Audio or Video File(s) - AIToys",
                filetypes=filetypes,
            )
            root.destroy()
            if paths:
                on_paths('\n'.join(paths))
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(f"File dialog error: {e}")

    threading.Thread(target=_run, daemon=True).start()
