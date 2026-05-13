from abc import ABC, abstractmethod
from typing import Optional

import requests


class SummarizerBackend(ABC):
    @abstractmethod
    def summarize(self, text: str, system_prompt: str) -> str:
        pass


class OpenAICompatibleSummarizerBackend(SummarizerBackend):
    def __init__(self, api_url: str, api_key: str = "", model: str = ""):
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def summarize(self, text: str, system_prompt: str) -> str:
        url = f"{self._api_url}/chat/completions"
        headers: dict = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        }

        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


class GeminiSummarizerBackend(SummarizerBackend):
    def __init__(self, api_key: str, model: str = "gemini-3-flash-preview"):
        self._api_key = api_key
        self._model = model

    def summarize(self, text: str, system_prompt: str) -> str:
        from google import genai  # pylint: disable=no-name-in-module
        from google.genai import types  # pylint: disable=no-name-in-module

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model=self._model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        return response.text.strip()


class Summarizer:
    _DEFAULT_PROMPT = "Summarize the following text concisely, preserving key information."

    def __init__(self) -> None:
        self._backend: Optional[SummarizerBackend] = None
        self._system_prompt = self._DEFAULT_PROMPT

    def set_backend(self, backend: SummarizerBackend) -> None:
        self._backend = backend

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def summarize(self, text: str, system_prompt: str = "") -> str:
        if self._backend is None:
            raise RuntimeError("No summarizer backend configured. Call set_backend() first.")
        prompt = system_prompt if system_prompt else self._system_prompt
        return self._backend.summarize(text, prompt)
