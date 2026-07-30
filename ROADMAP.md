# Groot — Project Roadmap

A self-hosted, offline-first personal AI assistant for coding and web development. Runs locally on your hardware by default; goes online only when you allow it — either for installing dependencies or for handing off a hard problem to a larger cloud model.

**Target hardware:** HP laptop, Intel Core i7 (6th gen), 16GB RAM, 4GB VRAM, 256GB SSD.
*Note: with only 4GB VRAM, most inference will run on CPU/RAM rather than GPU — expect a few seconds per response, not instant. The 256GB SSD is the tightest constraint; models and dependencies add up fast, so disk usage is tracked at every phase.*

---

## Phase 1 — Foundation
Get a model running locally and talking back.
- Install **Ollama** as the local model runner
- Pull a quantized coding model sized for this hardware — **Qwen2.5-Coder-7B-Instruct (Q4)** is the recommended starting point
- Verify basic chat works end-to-end before adding anything else

## Phase 2 — Memory
Give Groot the ability to remember things across sessions and across hardware.
- Stand up a local vector database (**Chroma** or **Qdrant**)
- Store conversations, coding preferences, and project context as retrievable memory
- Design the memory folder so it can be copied wholesale to a new machine later (this sets up Phase 7)

## Phase 3 — Personality & Voice
Shape how Groot talks.
- Write a system prompt defining tone, address style, and character (Jarvis-inspired: calm, precise, a little dry)
- Optional: add text-to-speech so it can respond out loud, not just in text

## Phase 4 — Tools & Permissions
Give Groot controlled access to your system — nothing automatic.
- File read/write access scoped to specific project folders
- Command execution, gated behind explicit confirmation
- An internet on/off switch: offline by default, toggled on only for things like installing packages, and only for that action

## Phase 5 — Agentic Layer
Move from single-turn answers to multi-step task execution.
- Task planning: break "build a landing page" into ordered steps
- Self-checking: run/lint/test its own output, catch and fix errors before handing back
- Tool selection: decide when a step needs a tool (file write, terminal, package install) versus a plain answer

## Phase 6 — Escape Hatch
Handle problems too hard for the local model.
- Add an optional call-out to a larger cloud model for specific hard tasks
- Keep this opt-in per task, not a default — the point is local-first, cloud-assisted

## Phase 7 — Portability
Make Groot movable.
- Package memory, system prompt, and config into one exportable bundle
- Document the restore process so a new laptop is back up to speed in minutes, not hours
