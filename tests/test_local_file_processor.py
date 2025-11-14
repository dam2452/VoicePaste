import pytest
from src.local_file_processor import LocalFileProcessor


def test_local_file_processor_initialization():
    processor = LocalFileProcessor()
    assert processor.temp_dir is not None


def test_is_valid_file_path_invalid_types():
    processor = LocalFileProcessor()

    invalid_inputs = [
        None,
        123,
        [],
        {},
        "",
    ]

    for input_val in invalid_inputs:
        assert processor.is_valid_file_path(input_val) is False


def test_is_valid_file_path_nonexistent_files():
    processor = LocalFileProcessor()

    nonexistent_files = [
        "C:\\nonexistent\\file.mp3",
        "/nonexistent/file.wav",
        "not_a_real_file.mp4",
    ]

    for file_path in nonexistent_files:
        assert processor.is_valid_file_path(file_path) is False


def test_is_valid_file_path_unsupported_extensions():
    processor = LocalFileProcessor()

    unsupported = [
        "file.txt",
        "document.pdf",
        "image.jpg",
        "data.csv",
    ]

    for file_path in unsupported:
        assert processor.is_valid_file_path(file_path) is False


def test_supported_audio_formats():
    processor = LocalFileProcessor()

    expected_audio = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
    assert processor.SUPPORTED_AUDIO == expected_audio


def test_supported_video_formats():
    processor = LocalFileProcessor()

    expected_video = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    assert processor.SUPPORTED_VIDEO == expected_video


def test_cleanup():
    processor = LocalFileProcessor()
    processor.cleanup()


@pytest.mark.skipif(True, reason="Requires actual audio/video file")
def test_process_file():
    processor = LocalFileProcessor()
    result = processor.process_file("C:\\path\\to\\test\\file.mp3")
    if result:
        audio_data, filename = result
        assert len(audio_data) > 0
        assert isinstance(filename, str)
    processor.cleanup()
