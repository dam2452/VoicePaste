from src.clipboard_manager import ClipboardManager


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
