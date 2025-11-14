import pytest
from src.youtube_downloader import YouTubeDownloader


def test_youtube_downloader_initialization():
    downloader = YouTubeDownloader()
    assert downloader.temp_dir is not None


def test_is_youtube_url_valid():
    downloader = YouTubeDownloader()

    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
    ]

    for url in valid_urls:
        assert downloader.is_youtube_url(url) is True


def test_is_youtube_url_invalid():
    downloader = YouTubeDownloader()

    invalid_urls = [
        "https://www.google.com",
        "https://vimeo.com/123456",
        "not a url",
        "",
        "ftp://youtube.com/video",
    ]

    for url in invalid_urls:
        assert downloader.is_youtube_url(url) is False


def test_cleanup():
    downloader = YouTubeDownloader()
    downloader.cleanup()


@pytest.mark.skipif(True, reason="Requires internet and actual YouTube video")
def test_download_audio():
    downloader = YouTubeDownloader()
    result = downloader.download_audio("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert result is not None
    audio_data, title = result
    assert len(audio_data) > 0
    assert isinstance(title, str)
    downloader.cleanup()
