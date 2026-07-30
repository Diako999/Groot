"""Thin wrapper around Ollama's local REST API. No network calls beyond localhost."""

from __future__ import annotations

from collections.abc import Iterator

import requests

from groot.config import Config


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: Config):
        self.model = config.model
        self.base_url = config.ollama_host.rstrip("/")

    def is_reachable(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.ok
        except requests.RequestException:
            return False

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        """Yield response text chunks for a chat turn."""
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {e}") from e

        for line in resp.iter_lines():
            if not line:
                continue
            import json

            chunk = json.loads(line)
            if chunk.get("error"):
                raise OllamaError(chunk["error"])
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
            if chunk.get("done"):
                break
