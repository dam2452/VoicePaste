import os
from unittest.mock import patch

from src.env_config import get, load_env


def test_get_existing_var():
    os.environ["TEST_VAR_XYZ"] = "hello"
    assert get("TEST_VAR_XYZ") == "hello"
    del os.environ["TEST_VAR_XYZ"]


def test_get_missing_var_returns_default():
    assert get("NONEXISTENT_VAR_XYZ") == ""
    assert get("NONEXISTENT_VAR_XYZ", "fallback") == "fallback"


def test_load_env_calls_dotenv():
    with patch("src.env_config.load_dotenv") as mock_load:
        load_env()
        mock_load.assert_called_once()
