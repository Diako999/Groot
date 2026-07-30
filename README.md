# Groot

A self-hosted, offline-first personal AI assistant for coding and web development.

Groot runs entirely on local hardware by default. It never calls out to the internet
unless you explicitly allow it — either to install a dependency or to hand off a hard
problem to a larger cloud model (Phase 6, not yet built).

See [ROADMAP.md](ROADMAP.md) for the full 7-phase build plan.

## Status

**Phase 1 — Foundation** (in progress): local model runner + basic chat.

## Requirements

- [Ollama](https://ollama.com) running locally
- Python 3.10+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python -m groot.cli chat
```

Chats with the local model over Ollama's REST API (`http://localhost:11434` by default).
No data leaves the machine.

## Project layout

```
groot/
├── cli.py             # `groot chat` entry point
├── config.py           # model name, Ollama host, etc.
└── ollama_client.py     # thin wrapper around Ollama's HTTP API
memory/                  # Phase 2+: local vector DB, gitignored
```
