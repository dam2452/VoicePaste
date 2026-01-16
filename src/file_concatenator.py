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

    def _on_timeout(self):
        with self._lock:
            if self.specific_files:
                self.on_status(f"Concatenating {len(self.specific_files)} specific files...")
                try:
                    result = concatenate_specific_files(file_paths=self.specific_files)
                    if self.on_complete:
                        self.on_complete(result)
                    file_count = result.count("# FILE:")
                    char_count = len(result)
                    self.on_status(f"Concatenation complete! {file_count} files, {char_count} chars copied to clipboard.")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.on_status(f"Error: {e}")
                finally:
                    self.reset()
                return

            if not self.folder_path or not self.extensions:
                self.on_status("Session expired: folder or extensions missing")
                self.reset()
                return

            self.on_status(f"Concatenating {len(self.extensions)} extension(s) from {self.folder_path}...")
            try:
                result = concatenate_files(
                    folder_path=self.folder_path,
                    extensions=list(self.extensions),
                )
                if self.on_complete:
                    self.on_complete(result)
                file_count = result.count("# FILE:")
                char_count = len(result)
                self.on_status(f"Concatenation complete! {file_count} files, {char_count} chars copied to clipboard.")
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.on_status(f"Error: {e}")
            finally:
                self.reset()

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
        return (f"Detected {len(unique_paths)} files, root: {self.folder_path}, "
                f"extensions: {', '.join(sorted(extensions))} - executing in 3s...")

    def process_clipboard(self, clipboard_text: str) -> str:
        with self._lock:
            lines = clipboard_text.strip().split('\n')
            if len(lines) > 1:
                result = self._process_multiple_files(lines)
                if result:
                    return result

            text = clipboard_text.strip().strip('"').strip("'")
            path = Path(text)

            if path.is_dir():
                self.folder_path = str(path.resolve())
                self.extensions = set()
                self._start_timer(self.folder_timeout)
                return f"Folder set: {self.folder_path} (waiting for extensions...)"

            if path.is_file():
                ext = path.suffix.lower()
                if ext:
                    if not self.folder_path:
                        self.folder_path = str(path.parent.resolve())
                        self.extensions.add(ext)
                        self._start_timer(self.extension_timeout)
                        return (f"Folder auto-set: {self.folder_path}, "
                                f"extension: {ext} - executing in 3s...")
                    self.extensions.add(ext)
                    self._start_timer(self.extension_timeout)
                    return f"Added extension: {ext} (total: {', '.join(sorted(self.extensions))}) - executing in 3s..."
                return "File has no extension"

            return f"Not a valid path: {text}"

    def get_status(self) -> str:
        if not self.folder_path:
            return "No folder set"
        if not self.extensions:
            return f"Folder: {self.folder_path} | No extensions yet"
        return f"Folder: {self.folder_path} | Extensions: {', '.join(sorted(self.extensions))}"


def show_concatenator_dialog(  # pylint: disable=too-many-locals,too-many-statements
    on_result: Optional[Callable[[str], None]] = None,
):
    import tkinter as tk  # pylint: disable=import-outside-toplevel
    from tkinter import (  # pylint: disable=import-outside-toplevel
        filedialog,
        ttk,
    )

    from src.dialog_utils import (  # pylint: disable=import-outside-toplevel
        center_dialog,
        create_dialog,
    )

    dialog, main_frame = create_dialog("File Concatenator", 550, 350)

    title_label = ttk.Label(
        main_frame,
        text="Concatenate Files for LLM Context",
        font=('Segoe UI', 11, 'bold'),
    )
    title_label.pack(pady=(0, 15))

    folder_frame = ttk.Frame(main_frame)
    folder_frame.pack(fill=tk.X, pady=5)

    ttk.Label(folder_frame, text="Folder:", width=12).pack(side=tk.LEFT)
    folder_var = tk.StringVar()
    folder_entry = ttk.Entry(folder_frame, textvariable=folder_var, width=40)
    folder_entry.pack(side=tk.LEFT, padx=5)

    def browse_folder():
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            folder_var.set(path)

    ttk.Button(folder_frame, text="Browse...", command=browse_folder).pack(side=tk.LEFT)

    ext_frame = ttk.Frame(main_frame)
    ext_frame.pack(fill=tk.X, pady=5)

    ttk.Label(ext_frame, text="Extensions:", width=12).pack(side=tk.LEFT)
    ext_var = tk.StringVar(value=".py .js .ts")
    ext_entry = ttk.Entry(ext_frame, textvariable=ext_var, width=48)
    ext_entry.pack(side=tk.LEFT, padx=5)

    exclude_frame = ttk.Frame(main_frame)
    exclude_frame.pack(fill=tk.X, pady=5)

    ttk.Label(exclude_frame, text="Exclude dirs:", width=12).pack(side=tk.LEFT)
    exclude_var = tk.StringVar()
    exclude_entry = ttk.Entry(exclude_frame, textvariable=exclude_var, width=48)
    exclude_entry.pack(side=tk.LEFT, padx=5)

    size_frame = ttk.Frame(main_frame)
    size_frame.pack(fill=tk.X, pady=5)

    ttk.Label(size_frame, text="Max file KB:", width=12).pack(side=tk.LEFT)
    size_var = tk.StringVar(value=str(DEFAULT_MAX_FILE_SIZE_KB))
    size_entry = ttk.Entry(size_frame, textvariable=size_var, width=10)
    size_entry.pack(side=tk.LEFT, padx=5)

    output_frame = ttk.Frame(main_frame)
    output_frame.pack(fill=tk.X, pady=5)

    ttk.Label(output_frame, text="Output file:", width=12).pack(side=tk.LEFT)
    output_var = tk.StringVar()
    output_entry = ttk.Entry(output_frame, textvariable=output_var, width=40)
    output_entry.pack(side=tk.LEFT, padx=5)

    def browse_output():
        path = filedialog.asksaveasfilename(
            title="Save Output As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            output_var.set(path)

    ttk.Button(output_frame, text="Browse...", command=browse_output).pack(side=tk.LEFT)

    options_frame = ttk.Frame(main_frame)
    options_frame.pack(fill=tk.X, pady=10)

    clipboard_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(options_frame, text="Copy to clipboard", variable=clipboard_var).pack(side=tk.LEFT, padx=10)

    summary_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(options_frame, text="Include summary", variable=summary_var).pack(side=tk.LEFT, padx=10)

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(main_frame, textvariable=status_var, foreground="gray")
    status_label.pack(pady=5)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=15)

    def on_run():
        folder = folder_var.get().strip()
        if not folder:
            status_var.set("Please select a folder")
            return

        extensions = ext_var.get().split()
        if not extensions:
            status_var.set("Please enter at least one extension")
            return

        exclude = [e.strip() for e in exclude_var.get().split() if e.strip()]

        try:
            max_size = int(size_var.get())
        except ValueError:
            max_size = DEFAULT_MAX_FILE_SIZE_KB

        status_var.set("Processing...")
        dialog.update()

        try:  # pylint: disable=too-many-try-statements
            result = concatenate_files(
                folder_path=folder,
                extensions=extensions,
                exclude_dirs=exclude,
                max_file_size_kb=max_size,
                include_summary=summary_var.get(),
            )

            output_path = output_var.get().strip()
            if output_path:
                Path(output_path).write_text(result, encoding='utf-8')
                status_var.set(f"Saved to {output_path}")

            if clipboard_var.get():
                import pyperclip  # pylint: disable=import-outside-toplevel
                pyperclip.copy(result)
                if output_path:
                    status_var.set(f"Saved to {output_path} and copied to clipboard!")
                else:
                    status_var.set("Copied to clipboard!")

            if on_result:
                on_result(result)

        except Exception as e:  # pylint: disable=broad-exception-caught
            status_var.set(f"Error: {e}")

    def on_cancel():
        dialog.destroy()

    ttk.Button(button_frame, text="Run", command=on_run, width=12).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=on_cancel, width=12).pack(side=tk.LEFT, padx=5)

    folder_entry.focus()
    center_dialog(dialog)
    dialog.mainloop()


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
