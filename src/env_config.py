import os

from dotenv import load_dotenv


def load_env() -> None:
    load_dotenv()


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)
