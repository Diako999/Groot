# Groot — Claude Code context

Self-hosted, offline-first personal AI coding assistant. Full plan: [ROADMAP.md](ROADMAP.md).
Read that file for the phase spec before starting any phase — don't re-derive it here.

## Hard constraints (never violate)

- **Offline by default.** No network calls except to `localhost:11434` (Ollama) unless
  the user explicitly enables internet for one action (install, or Phase 6 cloud escape hatch).
- **Ask before any download/install over ~2GB.**
- Target hardware: i7 6th-gen, 16GB RAM, 4GB VRAM, 256GB SSD (project lives on a ~44GB-free
  secondary volume — treat disk as tight).

## Stack

- Python 3 (3.14 on this machine), stdlib + `requests`, `typer`, `rich`, `PyYAML`.
- Ollama as the local model runner, accessed over its REST API — no heavy SDKs.
- Model: `qwen2.5-coder:7b-instruct-q4_K_M`.
- Phase 2+: Chroma (embedded, file-based) for memory — no server process, keeps the
  memory folder copyable to a new machine (Phase 7 requirement).
- Git remote: `https://github.com/Diako999/Groot.git`. Push after every completed step,
  not just at phase boundaries.

## Conventions

- Keep code clean and minimal — no speculative abstractions ahead of the phase that needs them.
- One module per concern in `groot/`: `config.py`, `ollama_client.py`, `cli.py`, and new
  modules per phase (e.g. `memory.py` in Phase 2, `tools.py` in Phase 4).
- Confirm with the user before moving to the next phase (per roadmap kickoff prompt).

## Status

- **Phase 1 (Foundation): in progress.** Scaffold done. Ollama install/model pull/chat
  verification pending user action — see task list.
- Phases 2–7: not started.

## Future requirements (noted now, built later)

- **Phase 4/5 — professional skills for Groot.** User wants Groot itself equipped with
  skills/capabilities for web dev, UI/UX, frontend, and backend work — not just raw chat.
  This only makes sense once Groot has tool access (Phase 4) and can plan/execute multi-step
  tasks (Phase 5). Don't install anything for this in Phase 1–3. When Phase 4/5 starts,
  design how Groot selects and invokes these capabilities (likely: a tool/skill registry
  it can call into, gated by the same permission system as file/command access).

- **Phase 4 — access model, decided.** User initially asked for full unrestricted
  file/command access by default with a toggle to restrict. Flagged that this contradicts
  the roadmap's own Phase 4 spec (gated by default, nothing automatic) and the risk of
  silent destructive actions. Decision: **gated by default**, with a session- or
  folder-scoped trust toggle the user can flip to stop being prompted for a while, and
  revoke anytime — mirrors the internet on/off switch already in the roadmap. Do not
  build "full access by default" — build the toggle as an escape from confirmation
  friction, not as a replacement for the default-deny posture.

Update this file's Status section (not this whole file) as phases complete, so a fresh
session can pick up state in one read instead of re-scanning history.
