from __future__ import annotations

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#89b4fa"
FG = "#cdd6f4"
DIM = "#6c7086"
BG = "#1e1e2e"
SURFACE = "#2a2a3d"
ERROR = "#f38ba8"
SUCCESS = "#a6e3a1"


def setup_window(win: ctk.CTk | ctk.CTkToplevel, title: str,
                 width: int, height: int) -> None:
    win.title(title)
    win.geometry(f"{width}x{height}")
    win.resizable(False, False)
    try:
        win.iconbitmap("icon.ico")
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    win.configure(fg_color=BG)
    win.update_idletasks()
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")
