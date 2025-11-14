from src.clipboard_manager import ClipboardManager
from pathlib import Path
import tempfile


def test_copy_to_clipboard():
    test_text = "Test transcription"
    result = ClipboardManager.copy_to_clipboard(test_text)
    assert result is True

    retrieved_text = ClipboardManager.get_from_clipboard()
    assert retrieved_text == test_text


def test_get_from_clipboard():
    test_text = "Another test"
    ClipboardManager.copy_to_clipboard(test_text)
    result = ClipboardManager.get_from_clipboard()
    assert result == test_text


def test_get_file_path_from_clipboard_with_text_path():
    temp_file = Path(tempfile.gettempdir()) / "test_voicepaste_clip.txt"
    temp_file.write_text("test")

    try:
        ClipboardManager.copy_to_clipboard(str(temp_file))
        file_path = ClipboardManager.get_file_path_from_clipboard()
        assert file_path == str(temp_file)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def test_get_file_path_from_clipboard_with_invalid_path():
    ClipboardManager.copy_to_clipboard("not_a_real_file_path.xyz")
    file_path = ClipboardManager.get_file_path_from_clipboard()
    assert file_path is None
