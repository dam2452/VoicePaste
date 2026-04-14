import argparse
import os
from pathlib import Path
import sys
import threading
from typing import (
    Callable,
    List,
    Optional,
    Set,
)

DEFAULT_EXCLUDE_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.idea', '.vs'}
SEPARATOR_LINE = '#' * 80
DEFAULT_MAX_FILE_SIZE_KB = 500
SESSION_TIMEOUT_FOLDER = 180.0
SESSION_TIMEOUT_EXTENSION = 3.0


def is_excluded(path: Path, exclude_dirs: set[str]) -> bool:
    return any(part in exclude_dirs for part in path.parts)


def read_file_safe(file_path: Path) -> Optional[str]:
    for encoding in ('utf-8', 'utf-8-sig', 'latin-1'):
        try:
            return file_path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def concatenate_specific_files(
    file_paths: List[Path],
    root: Optional[Path] = None,
    max_file_size_kb: int = DEFAULT_MAX_FILE_SIZE_KB,
    include_summary: bool = True,
) -> str:
    if not file_paths:
        return ""

    unique_paths = list({p.resolve(): p for p in file_paths}.values())

    if root is None:
        root = Path(os.path.commonpath([str(p) for p in unique_paths]))
        if root.is_file():
            root = root.parent

    max_size_bytes = max_file_size_kb * 1024
    collected_files = sorted(unique_paths, key=lambda p: str(p).lower())

    output_parts: list[str] = []
    skipped_files: list[str] = []
    processed_count = 0

    for file_path in collected_files:
        try:
            relative_path = file_path.relative_to(root)
        except ValueError:
            relative_path = file_path.name

        if file_path.stat().st_size > max_size_bytes:
            skipped_files.append(f"{relative_path} (too large)")
            continue

        content = read_file_safe(file_path)
        if content is None:
            skipped_files.append(f"{relative_path} (encoding error)")
            continue

        file_block = f"{SEPARATOR_LINE}\n# FILE: {relative_path}\n{SEPARATOR_LINE}\n{content}"
        if not content.endswith('\n'):
            file_block += '\n'
        output_parts.append(file_block)
        processed_count += 1

    result = '\n'.join(output_parts)

    if include_summary:
        extensions = {p.suffix.lower() for p in file_paths if p.suffix}
        summary_lines = [
            SEPARATOR_LINE,
            f"# SUMMARY: {processed_count} files concatenated",
            f"# Extensions: {', '.join(sorted(extensions))}",
            f"# Root: {root}",
        ]
        if skipped_files:
            summary_lines.append(f"# Skipped: {len(skipped_files)} files")
            for sf in skipped_files[:10]:
                summary_lines.append(f"#   - {sf}")
            if len(skipped_files) > 10:
                summary_lines.append(f"#   ... and {len(skipped_files) - 10} more")
        summary_lines.append(SEPARATOR_LINE)
        summary = '\n'.join(summary_lines)
        result = summary + '\n\n' + result

    return result


def concatenate_files(  # pylint: disable=too-many-locals
    folder_path: str,
    extensions: List[str],
    exclude_dirs: Optional[List[str]] = None,
    max_file_size_kb: int = DEFAULT_MAX_FILE_SIZE_KB,
    include_summary: bool = True,
) -> str:
    root = Path(folder_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Folder does not exist: {folder_path}")

    normalized_extensions = {ext if ext.startswith('.') else f'.{ext}' for ext in extensions}
    excluded = DEFAULT_EXCLUDE_DIRS | set(exclude_dirs or [])
    max_size_bytes = max_file_size_kb * 1024

    collected_files: list[Path] = []
    for ext in normalized_extensions:
        pattern = f'**/*{ext}'
        for file_path in root.glob(pattern):
            if file_path.is_file() and not is_excluded(file_path.relative_to(root), excluded):
                collected_files.append(file_path)

    collected_files = sorted(set(collected_files), key=lambda p: str(p.relative_to(root)).lower())

    output_parts: list[str] = []
    skipped_files: list[str] = []
    processed_count = 0

    for file_path in collected_files:
        relative_path = file_path.relative_to(root)

        if file_path.stat().st_size > max_size_bytes:
            skipped_files.append(f"{relative_path} (too large)")
            continue

        content = read_file_safe(file_path)
        if content is None:
            skipped_files.append(f"{relative_path} (encoding error)")
            continue

        file_block = f"{SEPARATOR_LINE}\n# FILE: {relative_path}\n{SEPARATOR_LINE}\n{content}"
        if not content.endswith('\n'):
            file_block += '\n'
        output_parts.append(file_block)
        processed_count += 1

    result = '\n'.join(output_parts)

    if include_summary:
        summary_lines = [
            SEPARATOR_LINE,
            f"# SUMMARY: {processed_count} files concatenated",
            f"# Extensions: {', '.join(sorted(normalized_extensions))}",
            f"# Root: {root}",
        ]
        if skipped_files:
            summary_lines.append(f"# Skipped: {len(skipped_files)} files")
            for sf in skipped_files[:10]:
                summary_lines.append(f"#   - {sf}")
            if len(skipped_files) > 10:
                summary_lines.append(f"#   ... and {len(skipped_files) - 10} more")
        summary_lines.append(SEPARATOR_LINE)
        summary = '\n'.join(summary_lines)
        result = summary + '\n\n' + result

    return result


class ConcatenatorSession:
    def __init__(
        self,
        on_complete: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        folder_timeout: float = SESSION_TIMEOUT_FOLDER,
        extension_timeout: float = SESSION_TIMEOUT_EXTENSION,
    ):
        self.folder_path: Optional[str] = None
        self.extensions: Set[str] = set()
        self.specific_files: List[Path] = []
        self.on_complete = on_complete
        self.on_status = on_status or print
        self.folder_timeout = folder_timeout
        self.extension_timeout = extension_timeout
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _start_timer(self, timeout: float):
        self._cancel_timer()
        self._timer = threading.Timer(timeout, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _run_concatenation(self):
        if self.specific_files:
            self.on_status(f"Concatenating {len(self.specific_files)} files...")
            try:
                result = concatenate_specific_files(file_paths=self.specific_files)
                if self.on_complete:
                    self.on_complete(result)
                file_count = result.count("# FILE:")
                self.on_status(f"Done: {file_count} files / {len(result)} chars copied to clipboard")
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.on_status(f"Concatenation error: {e}")
            finally:
                self.reset()
            return

        if not self.folder_path or not self.extensions:
            self.on_status("Session expired: folder or extensions missing")
            self.reset()
            return

        exts = ', '.join(sorted(self.extensions))
        self.on_status(f"Concatenating [{exts}] from {self.folder_path}...")
        try:
            result = concatenate_files(
                folder_path=self.folder_path,
                extensions=list(self.extensions),
            )
            if self.on_complete:
                self.on_complete(result)
            file_count = result.count("# FILE:")
            self.on_status(f"Done: {file_count} files / {len(result)} chars copied to clipboard")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.on_status(f"Concatenation error: {e}")
        finally:
            self.reset()

    def _on_timeout(self):
        with self._lock:
            self._run_concatenation()

    def reset(self):
        self._cancel_timer()
        self.folder_path = None
        self.extensions = set()
        self.specific_files = []

    def _find_common_root(self, paths: List[Path]) -> Optional[Path]:
        if not paths:
            return None
        if len(paths) == 1:
            return paths[0].parent
        try:
            common = Path(os.path.commonpath([str(p) for p in paths]))
            if common.is_file():
                common = common.parent
            return common if common.is_dir() else None
        except ValueError:
            return None

    def _process_multiple_files(self, lines: List[str]) -> Optional[str]:
        valid_paths: List[Path] = []
        extensions: Set[str] = set()

        for line in lines:
            cleaned = line.strip().strip('"').strip("'")
            if not cleaned:
                continue
            path = Path(cleaned)
            if path.is_file():
                valid_paths.append(path.resolve())
                ext = path.suffix.lower()
                if ext:
                    extensions.add(ext)

        if len(valid_paths) < 2:
            return None

        unique_paths = list({p: p for p in valid_paths}.values())
        common_root = self._find_common_root(unique_paths)
        if not common_root:
            return None

        self.specific_files = unique_paths
        self.folder_path = str(common_root)
        self.extensions = extensions
        self._start_timer(self.extension_timeout)
        return f"Will concat {len(unique_paths)} specific files from {self.folder_path} in 3s..."

    def process_clipboard(self, clipboard_text: str) -> str:
        with self._lock:
            lines = clipboard_text.strip().split('\n')
            if len(lines) > 1:
                result = self._process_multiple_files(lines)
                if result:
                    return result

            text = clipboard_text.strip().strip('"').strip("'")
            path = Path(text)

            if path.is_file():
                ext = path.suffix.lower()
                if not ext:
                    return "File has no extension"
                folder = str(path.parent.resolve())
                if not self.folder_path:
                    self.folder_path = folder
                self.extensions.add(ext)
                exts = ', '.join(sorted(self.extensions))
                self._start_timer(self.extension_timeout)
                return f"Will concat [{exts}] from {self.folder_path} in 3s..."

            return f"Not a valid path: {text}"

    def get_status(self) -> str:
        if not self.folder_path:
            return "No folder set"
        if not self.extensions:
            return f"Folder: {self.folder_path} | No extensions yet"
        return f"Folder: {self.folder_path} | Extensions: {', '.join(sorted(self.extensions))}"


def show_concatenator_dialog(  # pylint: disable=too-many-locals,too-many-statements
    on_result: Optional[Callable[[str], None]] = None,
    initial_folder: Optional[str] = None,
) -> None:
    import tkinter as tk  # pylint: disable=import-outside-toplevel
    from tkinter import filedialog  # pylint: disable=import-outside-toplevel

    import customtkinter as ctk  # pylint: disable=import-outside-toplevel
    from src.dialog_utils import (  # pylint: disable=import-outside-toplevel
        ACCENT, BG, DIM, ERROR, FG, SUCCESS, SURFACE, setup_window,
    )

    win = ctk.CTk()
    setup_window(win, "VoicePaste - File Concatenator", 620, 530)

    content = ctk.CTkFrame(win, fg_color=BG)
    content.pack(fill="both", expand=True, padx=24, pady=20)

    ctk.CTkLabel(content, text="File Concatenator", font=ctk.CTkFont(size=20, weight="bold"),
                 text_color=FG).pack(anchor="w")
    ctk.CTkLabel(content, text="Collect source files into a single block for LLM context.",
                 font=ctk.CTkFont(size=12), text_color=DIM).pack(anchor="w", pady=(2, 10))

    def labeled_entry(label: str, value: str = "", placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(content, text=label, font=ctk.CTkFont(size=12),
                     text_color=DIM, anchor="w").pack(fill="x")
        entry = ctk.CTkEntry(content, fg_color=SURFACE, border_color=SURFACE,
                             text_color=FG, placeholder_text=placeholder,
                             font=ctk.CTkFont(size=13), height=36)
        entry.pack(fill="x", pady=(2, 8))
        if value:
            entry.insert(0, value)
        return entry

    def labeled_entry_with_browse(label: str, value: str = "",
                                  placeholder: str = "",
                                  browse_fn: Optional[Callable] = None) -> ctk.CTkEntry:
        ctk.CTkLabel(content, text=label, font=ctk.CTkFont(size=12),
                     text_color=DIM, anchor="w").pack(fill="x")
        row = ctk.CTkFrame(content, fg_color=BG)
        row.pack(fill="x", pady=(2, 8))
        entry = ctk.CTkEntry(row, fg_color=SURFACE, border_color=SURFACE,
                             text_color=FG, placeholder_text=placeholder,
                             font=ctk.CTkFont(size=13), height=36)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if value:
            entry.insert(0, value)
        if browse_fn:
            ctk.CTkButton(row, text="Browse", command=browse_fn, width=80, height=36,
                          fg_color=SURFACE, text_color=FG, hover_color="#3a3a5c",
                          font=ctk.CTkFont(size=12)).pack(side="left")
        return entry

    def browse_folder() -> None:
        path = filedialog.askdirectory(title="Select folder to concatenate")
        if path:
            folder_entry.delete(0, "end")
            folder_entry.insert(0, path)

    def browse_output() -> None:
        path = filedialog.asksaveasfilename(
            title="Save output as...", defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            output_entry.delete(0, "end")
            output_entry.insert(0, path)

    folder_entry = labeled_entry_with_browse("Folder", value=initial_folder or "",
                                             placeholder="Path to folder...",
                                             browse_fn=browse_folder)
    ext_entry = labeled_entry("Extensions", value=".py .js .ts",
                              placeholder=".py .ts .md")
    exclude_entry = labeled_entry("Exclude dirs (space-separated)",
                                  placeholder="dist build tests .venv")

    size_row = ctk.CTkFrame(content, fg_color=BG)
    size_row.pack(fill="x", pady=(0, 8))
    ctk.CTkLabel(size_row, text="Max file size (KB)", font=ctk.CTkFont(size=12),
                 text_color=DIM).pack(side="left")
    size_entry = ctk.CTkEntry(size_row, fg_color=SURFACE, border_color=SURFACE,
                               text_color=FG, font=ctk.CTkFont(size=13), height=36, width=100)
    size_entry.pack(side="left", padx=8)
    size_entry.insert(0, str(DEFAULT_MAX_FILE_SIZE_KB))

    output_entry = labeled_entry_with_browse("Save to file (optional)",
                                             placeholder="Leave blank to only copy to clipboard",
                                             browse_fn=browse_output)

    opts_row = ctk.CTkFrame(content, fg_color=BG)
    opts_row.pack(fill="x", pady=(0, 12))
    clipboard_cb = ctk.CTkCheckBox(opts_row, text="Copy to clipboard",
                                   text_color=FG, fg_color=ACCENT, hover_color=ACCENT,
                                   font=ctk.CTkFont(size=13))
    clipboard_cb.select()
    clipboard_cb.pack(side="left", padx=(0, 20))
    summary_cb = ctk.CTkCheckBox(opts_row, text="Include summary header",
                                 text_color=FG, fg_color=ACCENT, hover_color=ACCENT,
                                 font=ctk.CTkFont(size=13))
    summary_cb.select()
    summary_cb.pack(side="left")

    status_label = ctk.CTkLabel(content, text="", font=ctk.CTkFont(size=12),
                                 text_color=DIM, anchor="w")
    status_label.pack(fill="x", pady=(0, 8))

    btn_row = ctk.CTkFrame(content, fg_color=BG)
    btn_row.pack(fill="x")

    def on_run() -> None:
        folder = folder_entry.get().strip()
        if not folder:
            status_label.configure(text="Select a folder first.", text_color=ERROR)
            return
        extensions = ext_entry.get().split()
        if not extensions:
            status_label.configure(text="Enter at least one extension.", text_color=ERROR)
            return
        exclude = exclude_entry.get().split()
        try:
            max_size = int(size_entry.get())
        except ValueError:
            max_size = DEFAULT_MAX_FILE_SIZE_KB

        status_label.configure(text="Processing...", text_color=DIM)
        run_btn.configure(state="disabled")
        win.update()

        try:  # pylint: disable=too-many-try-statements
            result = concatenate_files(
                folder_path=folder, extensions=extensions,
                exclude_dirs=exclude, max_file_size_kb=max_size,
                include_summary=bool(summary_cb.get()),
            )
            file_count = result.count("# FILE:")
            output_path = output_entry.get().strip()
            if output_path:
                Path(output_path).write_text(result, encoding="utf-8")
            if clipboard_cb.get():
                import pyperclip  # pylint: disable=import-outside-toplevel
                pyperclip.copy(result)
            if on_result:
                on_result(result)
            parts = [f"{file_count} files", f"{len(result):,} chars"]
            if clipboard_cb.get():
                parts.append("copied to clipboard")
            if output_path:
                parts.append(f"saved to {Path(output_path).name}")
            status_label.configure(text="Done: " + "  /  ".join(parts), text_color=SUCCESS)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            status_label.configure(text=f"Error: {exc}", text_color=ERROR)
        finally:
            run_btn.configure(state="normal")
            win.update()

    def on_cancel() -> None:
        win.destroy()

    ctk.CTkButton(btn_row, text="Cancel", command=on_cancel, width=110, height=44,
                  fg_color=SURFACE, text_color=FG, hover_color="#3a3a5c",
                  font=ctk.CTkFont(size=13)).pack(side="right")
    run_btn = ctk.CTkButton(btn_row, text="Run", command=on_run, width=110, height=44,
                            fg_color=ACCENT, text_color=BG, hover_color="#a8c8ff",
                            font=ctk.CTkFont(size=13, weight="bold"))
    run_btn.pack(side="right", padx=(0, 8))

    win.bind("<Return>", lambda _e: on_run())
    win.bind("<Escape>", lambda _e: on_cancel())

    if initial_folder:
        ext_entry.focus()
    else:
        folder_entry.focus()
    win.mainloop()


def main():
    parser = argparse.ArgumentParser(
        description='Concatenate files from a folder with ASCII separators for LLM context.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python file_concatenator.py ./src .py .js
  python file_concatenator.py ./project .py .ts --exclude dist build
  python file_concatenator.py ./code .py --max-size 1000 --output context.txt
  python file_concatenator.py --gui
''',
    )
    parser.add_argument('folder', nargs='?', help='Path to the folder to scan')
    parser.add_argument('extensions', nargs='*', help='File extensions to include (e.g., .py .js .ts)')
    parser.add_argument('--gui', '-g', action='store_true', help='Open GUI dialog')
    parser.add_argument('--exclude', '-e', nargs='*', default=[], help='Additional directories to exclude')
    parser.add_argument(
        '--max-size', '-m', type=int, default=DEFAULT_MAX_FILE_SIZE_KB,
        help=f'Maximum file size in KB (default: {DEFAULT_MAX_FILE_SIZE_KB})',
    )
    parser.add_argument('--output', '-o', help='Output file path (default: stdout)')
    parser.add_argument('--no-summary', action='store_true', help='Omit the summary header')
    parser.add_argument('--clipboard', '-c', action='store_true', help='Copy result to clipboard')

    args = parser.parse_args()

    if args.gui:
        show_concatenator_dialog()
        return

    if not args.folder:
        parser.error("folder is required (or use --gui)")
    if not args.extensions:
        parser.error("at least one extension is required (or use --gui)")

    try:
        result = concatenate_files(
            folder_path=args.folder,
            extensions=args.extensions,
            exclude_dirs=args.exclude,
            max_file_size_kb=args.max_size,
            include_summary=not args.no_summary,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"Output written to: {args.output}")
    else:
        print(result)

    if args.clipboard:
        try:
            import pyperclip  # pylint: disable=import-outside-toplevel
            pyperclip.copy(result)
            print("(Copied to clipboard)", file=sys.stderr)
        except ImportError:
            print("Warning: pyperclip not installed, clipboard copy skipped", file=sys.stderr)


if __name__ == '__main__':
    main()
