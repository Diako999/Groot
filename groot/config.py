"""Groot configuration: model, Ollama host, and paths.

Values can be overridden via config.yaml in the project root or
environment variables (env wins).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

DEFAULTS = {
    "model": "qwen2.5-coder:7b-instruct-q4_K_M",
    "ollama_host": "http://localhost:11434",
    "embedding_model": "nomic-embed-text",
}

MEMORY_DIR = PROJECT_ROOT / "memory" / "chroma"


@dataclass
class Config:
    model: str
    ollama_host: str
    embedding_model: str


def load_config() -> Config:
    values = dict(DEFAULTS)

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            file_values = yaml.safe_load(f) or {}
        values.update(file_values)

    values["model"] = os.environ.get("GROOT_MODEL", values["model"])
    values["ollama_host"] = os.environ.get("GROOT_OLLAMA_HOST", values["ollama_host"])
    values["embedding_model"] = os.environ.get("GROOT_EMBEDDING_MODEL", values["embedding_model"])

    return Config(**values)
