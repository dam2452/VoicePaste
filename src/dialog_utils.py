import tkinter as tk
from tkinter import ttk


def create_dialog(title: str, width: int = 500, height: int = 180) -> tuple[tk.Tk, ttk.Frame]:
    dialog = tk.Tk()
    dialog.title(title)
    dialog.geometry(f"{width}x{height}")
    dialog.resizable(False, False)

    try:
        dialog.iconbitmap(default='icon.ico')
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    dialog.configure(bg='#f0f0f0')

    main_frame = ttk.Frame(dialog, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    return dialog, main_frame


def center_dialog(dialog: tk.Tk):
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f'+{x}+{y}')
