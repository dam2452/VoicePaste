from datetime import datetime
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from src.dialog_utils import ACCENT, BG, DIM, ERROR, FG, SUCCESS, SURFACE, setup_window


class HistoryWindow:
    def __init__(
        self,
        get_history: Callable[[], List[Dict]],
        copy_from_history: Callable[[str], bool],
        delete_from_history: Callable[[str], bool],
    ):
        self._get_history = get_history
        self._copy_from_history = copy_from_history
        self._delete_from_history = delete_from_history
        self._window: Optional[ctk.CTk] = None
        self._is_open = False

    def show(self) -> None:
        if self._is_open:
            try:
                if self._window:
                    self._window.lift()
                    self._window.focus_force()
            except Exception:  # pylint: disable=broad-exception-caught
                self._is_open = False
            return
        threading.Thread(target=self._create_window, daemon=True).start()

    def _on_close(self) -> None:
        self._is_open = False
        if self._window:
            self._window.destroy()
        self._window = None

    def _create_window(self) -> None:  # pylint: disable=too-many-statements,too-many-locals
        self._is_open = True
        win = ctk.CTk()
        self._window = win
        setup_window(win, "VoicePaste - Transcription History", 1100, 680)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", self._on_close)

        all_items: List[Dict] = []
        selected_key: Dict[str, Optional[str]] = {"value": None}
        row_frames: List[ctk.CTkFrame] = []

        main = ctk.CTkFrame(win, fg_color=BG)
        main.pack(fill="both", expand=True, padx=20, pady=16)

        toolbar = ctk.CTkFrame(main, fg_color=BG)
        toolbar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(toolbar, text="Transcription History",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=FG).pack(side="left")

        search_var = tk.StringVar()
        search_var.trace("w", lambda *_: _apply_filters())
        search_entry = ctk.CTkEntry(toolbar, textvariable=search_var, width=260, height=34,
                                    placeholder_text="Search...", fg_color=SURFACE,
                                    border_color=SURFACE, text_color=FG,
                                    placeholder_text_color=DIM, font=ctk.CTkFont(size=12))
        search_entry.pack(side="left", padx=(20, 8))

        filter_var = tk.StringVar(value="all")
        source_filter = ctk.CTkOptionMenu(toolbar, variable=filter_var,
                                          values=["all", "voice", "youtube", "file"],
                                          command=lambda _v: _apply_filters(),
                                          fg_color=SURFACE, button_color=SURFACE,
                                          button_hover_color="#3a3a5c", text_color=FG,
                                          dropdown_fg_color=SURFACE, dropdown_text_color=FG,
                                          font=ctk.CTkFont(size=12), width=110, height=34)
        source_filter.pack(side="left")

        status_label = ctk.CTkLabel(toolbar, text="", font=ctk.CTkFont(size=12), text_color=DIM)
        status_label.pack(side="left", padx=16)

        ctk.CTkButton(toolbar, text="Refresh", command=lambda: _load(),
                      width=80, height=34, fg_color=SURFACE, text_color=FG,
                      hover_color="#3a3a5c", font=ctk.CTkFont(size=12)).pack(side="right")

        sep = ctk.CTkFrame(main, fg_color="#45475a", height=1)
        sep.pack(fill="x", pady=(0, 6))

        header = ctk.CTkFrame(main, fg_color=BG)
        header.pack(fill="x", padx=4, pady=(0, 4))
        for text, w in [("Date & Time", 155), ("Source", 80), ("Title", 230), ("Preview", 0)]:
            ctk.CTkLabel(header, text=text, font=ctk.CTkFont(size=11),
                         text_color=DIM, width=w, anchor="w").pack(side="left", padx=4)

        list_frame = ctk.CTkScrollableFrame(main, fg_color=BG, scrollbar_button_color=SURFACE,
                                            scrollbar_button_hover_color="#3a3a5c")
        list_frame.pack(fill="both", expand=True)

        sep2 = ctk.CTkFrame(main, fg_color="#45475a", height=1)
        sep2.pack(fill="x", pady=(6, 0))

        btn_bar = ctk.CTkFrame(main, fg_color=BG)
        btn_bar.pack(fill="x", pady=(10, 0))

        def _load() -> None:
            all_items.clear()
            all_items.extend(self._get_history())
            _apply_filters()

        def _apply_filters() -> None:
            q = search_var.get().lower()
            src = filter_var.get()
            filtered = [
                e for e in all_items
                if (src == "all" or e["source_type"] == src)
                and (not q or q in e["text"].lower() or q in e["title"].lower())
            ]
            for f in row_frames:
                f.destroy()
            row_frames.clear()

            for entry in filtered:
                key = entry["key"]
                date_str = datetime.fromtimestamp(entry["timestamp"]).strftime("%Y-%m-%d  %H:%M")
                src_text = entry["source_type"].capitalize()
                preview = entry["text"][:140].replace("\n", " ")
                if len(entry["text"]) > 140:
                    preview += "..."

                is_sel = selected_key["value"] == key
                row_bg = SURFACE if is_sel else BG
                row = ctk.CTkFrame(list_frame, fg_color=row_bg, corner_radius=6)
                row.pack(fill="x", pady=2, padx=2)
                row_frames.append(row)

                src_colors = {"Voice": "#a6e3a1", "Youtube": "#f38ba8", "File": "#89b4fa"}
                src_color = src_colors.get(src_text, ACCENT)

                ctk.CTkLabel(row, text=date_str, font=ctk.CTkFont(size=11), text_color=DIM,
                             width=155, anchor="w").pack(side="left", padx=4, pady=8)
                ctk.CTkLabel(row, text=src_text, font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=src_color, width=80, anchor="w").pack(side="left", padx=4)
                ctk.CTkLabel(row, text=entry["title"], font=ctk.CTkFont(size=12),
                             text_color=FG, width=230, anchor="w").pack(side="left", padx=4)
                ctk.CTkLabel(row, text=preview, font=ctk.CTkFont(size=11),
                             text_color=DIM, anchor="w").pack(side="left", padx=4, fill="x", expand=True)

                row.bind("<Button-1>", lambda _e, k=key: _select(k))
                for child in row.winfo_children():
                    child.bind("<Button-1>", lambda _e, k=key: _select(k))
                    child.bind("<Double-Button-1>", lambda _e, k=key: _copy_key(k))

            status_label.configure(text=f"{len(filtered)} of {len(all_items)} entries")
            win.update_idletasks()

        def _select(key: str) -> None:
            selected_key["value"] = key
            _apply_filters()

        def _copy_key(key: str) -> None:
            self._copy_from_history(key)
            status_label.configure(text="Copied to clipboard.", text_color=SUCCESS)
            win.after(2000, lambda: status_label.configure(text=f"", text_color=DIM))

        def _on_copy() -> None:
            if not selected_key["value"]:
                status_label.configure(text="Select an entry first.", text_color=ERROR)
                return
            _copy_key(selected_key["value"])

        def _on_export() -> None:
            if not selected_key["value"]:
                status_label.configure(text="Select an entry first.", text_color=ERROR)
                return
            entry = next((e for e in all_items if e["key"] == selected_key["value"]), None)
            if not entry:
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Export Transcription",
            )
            if path:
                date_str = datetime.fromtimestamp(entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"{'=' * 80}\n{entry['title']}\nSource: {entry['source_type']}\n"
                            f"Date: {date_str}\n{'=' * 80}\n\n{entry['text']}\n")
                status_label.configure(text=f"Saved to {path}", text_color=SUCCESS)

        def _on_delete() -> None:
            if not selected_key["value"]:
                status_label.configure(text="Select an entry first.", text_color=ERROR)
                return
            if messagebox.askyesno("Confirm Delete",
                                   "Delete this transcription?\nThis cannot be undone."):
                self._delete_from_history(selected_key["value"])
                selected_key["value"] = None
                _load()

        ctk.CTkButton(btn_bar, text="Copy to Clipboard", command=_on_copy,
                      height=36, fg_color=ACCENT, text_color=BG, hover_color="#a8c8ff",
                      font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="Export", command=_on_export,
                      height=36, fg_color=SURFACE, text_color=FG, hover_color="#3a3a5c",
                      font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="Delete", command=_on_delete,
                      height=36, fg_color="#45475a", text_color="#f38ba8", hover_color="#5a3a3a",
                      font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkLabel(btn_bar, text="Click to select  |  Double-click to copy",
                     font=ctk.CTkFont(size=11), text_color=DIM).pack(side="right")

        _load()
        win.mainloop()
