import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import (
    filedialog,
    messagebox,
    ttk,
)
from typing import Callable


class HistoryWindow:
    def __init__(
        self,
        get_history: Callable,
        copy_from_history: Callable,
        delete_from_history: Callable,
    ):
        self.get_history = get_history
        self.copy_from_history = copy_from_history
        self.delete_from_history = delete_from_history
        self.window = None
        self.tree = None
        self.search_var = None
        self.filter_var = None
        self.all_items = []
        self.is_open = False

    def show(self):
        if self.is_open:
            try:
                if self.window is not None:
                    self.window.lift()
                    self.window.focus_force()
            except Exception:  # pylint: disable=broad-exception-caught
                self.is_open = False
            return

        threading.Thread(target=self._create_window, daemon=True).start()

    def _on_close(self):
        self.is_open = False
        if self.window:
            self.window.destroy()
        self.window = None

    def _create_window(self):
        self.is_open = True
        self.window = tk.Tk()
        self.window.title("VoicePaste - Transcription History")
        self.window.geometry("1200x700")

        try:
            self.window.iconbitmap(default='icon.ico')
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(toolbar_frame, text="Search:", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._apply_filters())
        search_entry = ttk.Entry(toolbar_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(toolbar_frame, text="Filter:", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value="all")
        filter_combo = ttk.Combobox(
            toolbar_frame,
            textvariable=self.filter_var,
            values=["all", "voice", "youtube", "file"],
            state="readonly",
            width=15,
        )
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())

        refresh_btn = ttk.Button(toolbar_frame, text="Refresh", command=self._load_history, width=10)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        columns = ("date", "type", "title", "preview")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
        )

        scrollbar_y.config(command=self.tree.yview)
        scrollbar_x.config(command=self.tree.xview)

        self.tree.heading("date", text="Date & Time")
        self.tree.heading("type", text="Source")
        self.tree.heading("title", text="Title")
        self.tree.heading("preview", text="Text Preview")

        self.tree.column("date", width=150, minwidth=150)
        self.tree.column("type", width=80, minwidth=80)
        self.tree.column("title", width=250, minwidth=200)
        self.tree.column("preview", width=600, minwidth=300)

        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind('<Double-Button-1>', lambda e: self._copy_selected())

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Copy to Clipboard", command=self._copy_selected, width=18).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Selected", command=self._export_selected, width=18).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Delete Selected", command=self._delete_selected, width=18).pack(side=tk.LEFT, padx=(0, 5))

        status_label = ttk.Label(button_frame, text="Double-click item to copy | Right-click for context menu", font=('Segoe UI', 8), foreground='gray')
        status_label.pack(side=tk.RIGHT)

        self._create_context_menu()
        self._load_history()

        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f'+{x}+{y}')

        self.window.mainloop()

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Copy to Clipboard", command=self._copy_selected)
        self.context_menu.add_command(label="Export Selected", command=self._export_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Selected", command=self._delete_selected)

        self.tree.bind('<Button-3>', self._show_context_menu)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _load_history(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.all_items = []
        history = self.get_history()

        for entry in history:
            date_str = datetime.fromtimestamp(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            source_type = entry['source_type'].capitalize()
            title = entry['title']
            preview = entry['text'][:100] + "..." if len(entry['text']) > 100 else entry['text']

            item_id = self.tree.insert(
                '',
                'end',
                values=(date_str, source_type, title, preview),
                tags=(entry['key'],),
            )
            self.all_items.append({
                'item_id': item_id,
                'key': entry['key'],
                'data': entry,
            })

        self._apply_filters()

    def _apply_filters(self):
        search_text = self.search_var.get().lower() if self.search_var else ""
        filter_type = self.filter_var.get() if self.filter_var else "all"

        for item in self.all_items:
            entry = item['data']
            item_id = item['item_id']

            type_match = filter_type == "all" or entry['source_type'] == filter_type

            text_match = (
                search_text == "" or
                search_text in entry['text'].lower() or
                search_text in entry['title'].lower()
            )

            if type_match and text_match:
                self.tree.reattach(item_id, '', 'end')
            else:
                self.tree.detach(item_id)

    def _get_selected_key(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item first.")
            return None

        item = selection[0]
        tags = self.tree.item(item, 'tags')
        if tags:
            return tags[0]
        return None

    def _copy_selected(self):
        key = self._get_selected_key()
        if key:
            if self.copy_from_history(key):
                messagebox.showinfo("Success", "Transcription copied to clipboard!")

    def _export_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select at least one item to export.")
            return

        selected_items = []
        for item in selection:
            tags = self.tree.item(item, 'tags')
            if tags:
                key = tags[0]
                for stored_item in self.all_items:
                    if stored_item['key'] == key:
                        selected_items.append(stored_item['data'])
                        break

        if not selected_items:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("All files", "*.*"),
            ],
            title="Export Transcriptions",
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for idx, item in enumerate(selected_items, 1):
                        date_str = datetime.fromtimestamp(item['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"{'=' * 80}\n")
                        f.write(f"Entry {idx}: {item['title']}\n")
                        f.write(f"Source: {item['source_type'].capitalize()}\n")
                        f.write(f"Date: {date_str}\n")
                        f.write(f"{'=' * 80}\n\n")
                        f.write(item['text'])
                        f.write("\n\n")

                messagebox.showinfo("Success", f"Exported {len(selected_items)} transcription(s) to:\n{file_path}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                messagebox.showerror("Error", f"Failed to export: {e}")

    def _delete_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select at least one item to delete.")
            return

        count = len(selection)
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {count} item(s)?\nThis action cannot be undone.",
        )

        if result:
            for item in selection:
                tags = self.tree.item(item, 'tags')
                if tags:
                    key = tags[0]
                    self.delete_from_history(key)

            self._load_history()
            messagebox.showinfo("Success", f"Deleted {count} item(s) from history.")
