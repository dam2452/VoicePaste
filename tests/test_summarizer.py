from unittest.mock import MagicMock, patch

from src.summarizer import Summarizer


def test_summarizer_defaults():
    s = Summarizer()
    assert s._api_url == ""
    assert s._model == ""
    assert "Summarize" in s._system_prompt


def test_summarizer_configure():
    s = Summarizer()
    s.configure(
        api_url="http://localhost:11434/v1",
        api_key="test-key",
        model="llama3",
        system_prompt="Custom prompt",
    )
    assert s._api_url == "http://localhost:11434/v1"
    assert s._api_key == "test-key"
    assert s._model == "llama3"
    assert s._system_prompt == "Custom prompt"


def test_summarizer_configure_strips_trailing_slash():
    s = Summarizer()
    s.configure(api_url="http://localhost:11434/v1/", api_key="", model="m")
    assert s._api_url == "http://localhost:11434/v1"


def test_summarizer_summarize_success():
    s = Summarizer()
    s.configure(api_url="http://localhost:11434/v1", api_key="k", model="llama3")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Short summary."}}],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("src.summarizer.requests.post", return_value=mock_resp) as mock_post:
        result = s.summarize("Long text to summarize")

    assert result == "Short summary."
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[1]["json"]["model"] == "llama3"
    assert call_kwargs[1]["json"]["messages"][0]["role"] == "system"
    assert call_kwargs[1]["json"]["messages"][1]["content"] == "Long text to summarize"


def test_summarizer_sends_api_key():
    s = Summarizer()
    s.configure(api_url="http://localhost:11434/v1", api_key="my-key", model="m")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.summarizer.requests.post", return_value=mock_resp) as mock_post:
        s.summarize("text")

    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer my-key"


def test_summarizer_no_api_key_no_auth_header():
    s = Summarizer()
    s.configure(api_url="http://localhost:11434/v1", api_key="", model="m")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.summarizer.requests.post", return_value=mock_resp) as mock_post:
        s.summarize("text")

    headers = mock_post.call_args[1]["headers"]
    assert "Authorization" not in headers
