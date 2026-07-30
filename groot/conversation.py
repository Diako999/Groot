"""Shared conversation-turn logic used by both the interactive CLI chat and the
always-on voice listener, so persona/memory wiring lives in one place."""

from __future__ import annotations

from collections.abc import Iterator

from groot.config import Config
from groot.memory import MemoryStore
from groot.ollama_client import OllamaClient
from groot.persona import load_persona


class GrootSession:
    def __init__(self, config: Config):
        self.client = OllamaClient(config)
        self.memory = MemoryStore(config)
        self.persona = {"role": "system", "content": load_persona()}
        self.history: list[dict] = []

    def turn(self, user_input: str) -> Iterator[str]:
        """Yield streamed response chunks for one conversation turn."""
        self.history.append({"role": "user", "content": user_input})

        remembered = self.memory.query(user_input)
        messages = [self.persona] + self.history
        if remembered:
            context_block = "\n".join(f"- {m}" for m in remembered)
            messages = [
                self.persona,
                {
                    "role": "system",
                    "content": f"Relevant memory from past sessions:\n{context_block}",
                },
            ] + self.history

        reply = ""
        try:
            for chunk in self.client.stream_chat(messages):
                reply += chunk
                yield chunk
        except Exception:
            self.history.pop()
            raise

        self.history.append({"role": "assistant", "content": reply})
        self.memory.add(f"User: {user_input}", category="conversation")
        self.memory.add(f"Groot: {reply}", category="conversation")
