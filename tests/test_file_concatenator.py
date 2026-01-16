from pathlib import Path
import tempfile
import time

from src.file_concatenator import (
    ConcatenatorSession,
    concatenate_files,
    is_excluded,
    read_file_safe,
)


def test_concatenate_single_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('hello')\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py'], include_summary=False)

        assert "# FILE: test.py" in result
        assert "print('hello')" in result


def test_concatenate_multiple_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.py").write_text("# file a\n", encoding='utf-8')
        (Path(tmpdir) / "b.py").write_text("# file b\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py'], include_summary=False)

        assert "# FILE: a.py" in result
        assert "# FILE: b.py" in result
        assert result.index("a.py") < result.index("b.py")


def test_concatenate_nested_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir) / "sub" / "nested"
        subdir.mkdir(parents=True)
        (subdir / "deep.py").write_text("# deep\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py'], include_summary=False)

        assert "sub/nested/deep.py" in result.replace('\\', '/') or "sub\\nested\\deep.py" in result


def test_concatenate_excludes_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text("# main\n", encoding='utf-8')
        excluded = Path(tmpdir) / "__pycache__"
        excluded.mkdir()
        (excluded / "cached.py").write_text("# cached\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py'], include_summary=False)

        assert "main.py" in result
        assert "cached.py" not in result


def test_concatenate_multiple_extensions():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "script.py").write_text("# py\n", encoding='utf-8')
        (Path(tmpdir) / "app.js").write_text("// js\n", encoding='utf-8')
        (Path(tmpdir) / "data.txt").write_text("text\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py', '.js'], include_summary=False)

        assert "script.py" in result
        assert "app.js" in result
        assert "data.txt" not in result


def test_concatenate_with_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("pass\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py'], include_summary=True)

        assert "SUMMARY:" in result
        assert "1 files concatenated" in result


def test_concatenate_skips_large_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        small = Path(tmpdir) / "small.py"
        small.write_text("# small\n", encoding='utf-8')
        large = Path(tmpdir) / "large.py"
        large.write_text("x" * 2000, encoding='utf-8')

        result = concatenate_files(tmpdir, ['.py'], max_file_size_kb=1, include_summary=True)

        assert "small.py" in result
        assert "large.py" not in result or "too large" in result


def test_is_excluded():
    assert is_excluded(Path("__pycache__/test.py"), {"__pycache__"})
    assert is_excluded(Path("src/__pycache__/test.py"), {"__pycache__"})
    assert not is_excluded(Path("src/main.py"), {"__pycache__"})


def test_read_file_safe_utf8():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello", encoding='utf-8')
        assert read_file_safe(test_file) == "hello"


def test_read_file_safe_latin1():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_bytes(b'\xe9\xe8\xe0')
        content = read_file_safe(test_file)
        assert content is not None


def test_concatenate_extension_without_dot():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("pass\n", encoding='utf-8')

        result = concatenate_files(tmpdir, ['py'], include_summary=False)

        assert "test.py" in result


def test_session_set_folder():
    with tempfile.TemporaryDirectory() as tmpdir:
        session = ConcatenatorSession()
        msg = session.process_clipboard(tmpdir)

        assert "Folder set:" in msg
        assert session.folder_path == str(Path(tmpdir).resolve())


def test_session_add_extension():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("pass\n", encoding='utf-8')
        session = ConcatenatorSession()
        session.process_clipboard(tmpdir)

        msg = session.process_clipboard(str(Path(tmpdir) / "test.py"))

        assert "Added extension: .py" in msg
        assert ".py" in session.extensions


def test_session_auto_sets_folder_from_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("pass\n", encoding='utf-8')
        session = ConcatenatorSession()

        msg = session.process_clipboard(str(Path(tmpdir) / "test.py"))

        assert "Folder auto-set" in msg
        assert session.folder_path is not None
        assert ".py" in session.extensions


def test_session_invalid_path():
    session = ConcatenatorSession()
    msg = session.process_clipboard("/nonexistent/path/xyz")
    assert "Not a valid path" in msg


def test_session_reset():
    with tempfile.TemporaryDirectory() as tmpdir:
        session = ConcatenatorSession()
        session.process_clipboard(tmpdir)
        session.reset()

        assert session.folder_path is None
        assert len(session.extensions) == 0


def test_session_multiple_extensions():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.py").write_text("pass\n", encoding='utf-8')
        (Path(tmpdir) / "b.js").write_text("//\n", encoding='utf-8')

        session = ConcatenatorSession()
        session.process_clipboard(tmpdir)
        session.process_clipboard(str(Path(tmpdir) / "a.py"))
        session.process_clipboard(str(Path(tmpdir) / "b.js"))

        assert ".py" in session.extensions
        assert ".js" in session.extensions


def test_session_timeout_triggers_concatenation():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("# content\n", encoding='utf-8')

        result_holder = {'result': None}

        def on_complete(result):
            result_holder['result'] = result

        session = ConcatenatorSession(on_complete=on_complete, extension_timeout=0.1)
        session.process_clipboard(tmpdir)
        session.process_clipboard(str(Path(tmpdir) / "test.py"))

        time.sleep(0.3)

        result = result_holder['result']
        assert result is not None
        assert "test.py" in str(result)


def test_session_get_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("pass\n", encoding='utf-8')

        session = ConcatenatorSession()
        assert "No folder set" in session.get_status()

        session.process_clipboard(tmpdir)
        assert "No extensions yet" in session.get_status()

        session.process_clipboard(str(Path(tmpdir) / "test.py"))
        assert ".py" in session.get_status()


def test_session_multiple_files_in_clipboard():
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir) / "src"
        subdir.mkdir()
        (subdir / "a.py").write_text("# a\n", encoding='utf-8')
        (subdir / "b.py").write_text("# b\n", encoding='utf-8')
        (subdir / "c.js").write_text("// c\n", encoding='utf-8')

        clipboard_text = f"{subdir / 'a.py'}\n{subdir / 'b.py'}\n{subdir / 'c.js'}"

        session = ConcatenatorSession()
        msg = session.process_clipboard(clipboard_text)

        assert "Detected 3 files" in msg
        assert ".py" in session.extensions
        assert ".js" in session.extensions
        assert session.folder_path is not None
