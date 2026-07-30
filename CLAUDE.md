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

## Environment gotchas (hard-won, don't re-discover)

- **This machine's `/tmp` is a 7.4GB tmpfs (RAM-backed).** Any large pip install or
  download must set `TMPDIR` to a path on the actual disk (e.g. the project directory)
  or it fails with a misleading "Disk quota exceeded" error.
- **Main runtime venv (`groot/.venv`) is Python 3.14.** Very new — many ML packages lag on
  wheel support. Training tooling (Phase 3 voice) needed a **separate Python 3.11 venv**
  (`training/.venv-train`) because `piper-phonemize` has no 3.14 (or even 3.12) Linux wheel,
  only cp39-cp311. Check wheel availability (`pip index versions`, or the PyPI simple index)
  before assuming a pinned package will install on whatever Python happens to be current.
- **Always force CPU-only PyTorch explicitly**: `pip install torch --index-url
  https://download.pytorch.org/whl/cpu`. Plain `pip install torch` (or anything that pulls
  torch transitively, e.g. resemblyzer, torch-audiomentations) resolves the CUDA build by
  default, dragging in several GB of NVIDIA CUDA runtime packages this hardware (4GB VRAM)
  doesn't need. This bit us twice — once for the main venv, once for the training venv, and
  a third time when `torch-audiomentations` silently reinstalled a CUDA-linked `torchaudio`
  even after torch itself was CPU-only. After installing anything torch-adjacent, verify with
  `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
- **`git clone` over HTTPS to github.com times out on this network**, even though plain
  HTTPS GET/HEAD to github.com works fine. Use `codeload.github.com/<org>/<repo>/tar.gz/refs/heads/<branch>`
  (or `refs/tags/<tag>`) tarball downloads instead of `git clone`. Same family of issue as
  `ollama.com` returning 403 while `registry.ollama.ai` works — this network/ISP seems to
  selectively break specific protocols/hosts, not a blanket block.
- **Old pinned ML package versions vs. a fresh environment = frequent breakage.** Hit this
  repeatedly setting up openWakeWord's custom training pipeline (dscripka/openWakeWord,
  cloned from GitHub — the pip package doesn't include training scripts): `tensorflow-cpu==2.8.1`
  has no wheel for anything remotely current (skip it — only needed for optional TFLite
  export via `--convert_to_tflite`, ONNX-only is fine for a PC); `datasets==2.14.6` breaks
  against modern `pyarrow` (upgrade to latest `datasets` instead of fighting the pin);
  newer `datasets` moved audio decoding to a separate `torchcodec` package which itself
  needs system FFmpeg (`sudo apt install ffmpeg`) and returns an `AudioDecoder` object
  (`.get_all_samples()` → `.data`/`.sample_rate`) rather than the old `{"path","array"}`
  dict; `rudraml/fma` uses a deprecated dataset-loading-script format HF no longer supports
  at all (switched to `ashraq/esc50` instead). General lesson: when a tutorial/notebook pins
  exact versions from ~2023, expect several of them to be dead on arrival in 2026 — check
  each one rather than installing the full pinned list blind.
- **`piper-sample-generator` breaking change**: current PyPI release (3.2.0) was refactored
  into a CLI package and no longer has the top-level `generate_samples.py` script/function
  that openWakeWord's `train.py` imports directly (`from generate_samples import
  generate_samples`). Use the `v2.0.0` tag instead (matches the LibriTTS checkpoint release
  openWakeWord's pipeline expects anyway) - download via codeload tarball, not pip install.
  Also needed one manual patch: `torch.load(model_path)` → add `weights_only=False` (PyTorch
  2.6+ changed the default; fine since the checkpoint is from the official GitHub release).

## Status

- **Phase 1 (Foundation): complete.** Ollama installed (v0.32.5, via GitHub release —
  ollama.com's website returns 403 on this network, but registry.ollama.ai works fine for
  pulls), running as a systemd service. Model `qwen2.5-coder:7b-instruct-q4_K_M` pulled
  (4.7GB). `python -m groot.cli` verified working end-to-end (no `chat` subcommand needed —
  Typer collapses to single-command mode with only one command registered).
- **Phase 2 (Memory): complete.** `groot/memory.py` — Chroma PersistentClient at
  `memory/chroma/`, embeddings via Ollama's `nomic-embed-text` (274MB, pulled) through a
  custom `OllamaEmbeddingFunction` (must inherit `chromadb.api.types.EmbeddingFunction`,
  not just structurally match it, or `embed_query` is missing at query time). Wired into
  `cli.py`: query relevant memories before each model call (injected as a system message,
  not persisted back into `history`), store both sides of every turn after. Verified
  retrieval works across a brand-new process (not just same-session history) — a fact
  stated in one `groot` invocation was correctly recalled in a completely separate one.
- **Phase 3 (Personality & Voice): in progress.**
  - Persona (`persona.txt` + `groot/persona.py`): done, verified tone shift in output.
  - Chat/memory logic refactored into `groot/conversation.py` (`GrootSession`), shared by
    both `groot chat` and the voice listener — avoids duplicating persona/memory wiring.
  - Voice stack decided and installed in the **main** venv (Python 3.14):
    `openwakeword`, `sounddevice` (+ system `libportaudio2`), `resemblyzer` (CPU-only
    torch, forced via `--index-url https://download.pytorch.org/whl/cpu`),
    `faster-whisper` (STT, model `small.en`, downloads from HF on first use).
  - Speaker enrollment/verification: `groot/speaker.py` + `groot/audio_io.py`, wired as
    `python -m groot.cli enroll`. Voiceprint saved to `voiceprint.npy` (gitignored,
    biometric data). Sanity-tested with synthetic TTS voices (not yet with the user's
    real voice — do that once the wake-word model is ready).
  - STT: `groot/stt.py` wraps faster-whisper. Verified end-to-end: transcribed a
    synthetic "hey groot" sample correctly.
  - Always-on listener: `groot/listen.py`, wired as `python -m groot.cli listen`. Combines
    wake-word detection → speaker verification → STT → `GrootSession.turn()`. Written but
    **not yet tested against a real trained model or live mic** — blocked on training.
  - systemd user service drafted at `systemd/groot-listen.service` (paths quoted because
    the project lives under a space-containing path outside `$HOME`, so `%h` doesn't
    apply). **Not yet installed/enabled** — do that only after the model is trained and
    voice is enrolled and confirmed working via manual `groot listen` first.
  - **Custom "Hey Groot" wake-word training** (user chose the full official openWakeWord
    pipeline over the lighter few-shot approach, after seeing it needs a 16GB dataset):
    training assets live under `training/` (gitignored — scratch data, not the product).
    Separate Python 3.11 venv at `training/.venv-train` (see wheel-availability gotcha
    above). Config at `training/hey_groot.yml`.
    **Status: pipeline fully debugged and validated end-to-end via a 100-step calibration
    run — paused before the real run at user's request (it was very late; resume by just
    launching the full run, nothing else left to fix).** `--generate_clips` and
    `--augment_clips` are both genuinely complete (verify: `training/my_custom_model/
    hey_groot/*.npy` should have all 4 feature files — positive/negative × train/test;
    if only `positive_features_train.npy` exists, a prior run was interrupted and you
    need `--augment_clips --overwrite` to regenerate all 4, since train.py's own
    completeness check only looks at that one file). The 16GB
    `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` is fully downloaded. Next and
    final step: `--train_model` (steps: 50000 in config). Calibration (100 steps) measured
    steady-state throughput at ~2.5 it/s on this CPU-only i7 6th-gen box → **full run
    estimated ~5.5-6 hours**, plan for it to run unattended in the background.
    **Local patches applied to the cloned `training/openwakeword-src/openwakeword/
    train.py`** (gitignored, so redo these if the clone is ever refreshed/re-cloned):
    1) `scipy.special.sph_harm` compat shim (renamed to `sph_harm_y`, only
    `acoustics.generator.noise()` is actually used, unrelated to the broken
    directivity code path this satisfies the import for);
    2) `torchaudio.info` compat shim via `soundfile` (torch_audiomentations 0.12.0 still
    calls it; newer torchaudio removed it with no replacement);
    3) **critical memory fix**: reduced the hardcoded `DataLoader(num_workers=os.cpu_count()//2,
    prefetch_factor=16)` down to `num_workers=2, prefetch_factor=2`, and changed the
    false-positive validation sliding-window stride from `1` (fully overlapping, builds a
    ~3GB array from a 176MB file) to `input_shape[0]` (non-overlapping, ~1/16th the
    memory) — without this, a real run exhausted all 14GB RAM + 4GB swap on this machine
    before training even started;
    4) fixed `argparse` defaults (`default="False"` as a *string* is truthy in Python, so
    `--convert_to_tflite` and friends always evaluated true regardless of the flag —
    changed to real `default=False`); this was silently trying to convert to TFLite (which
    needs `tensorflow-cpu`, deliberately not installed — see wheel-availability gotcha)
    even though we only want ONNX for PC use;
    5) installed `onnxscript` (newer torch's ONNX exporter needs it, wasn't a
    `piper-sample-generator`/`train.py` requirements-file dependency).
    **Once training finishes, copy the final `hey_groot.onnx` out of `training/` into a
    git-tracked `models/` folder** (training/ itself is gitignored scratch space, but the
    trained model is a real runtime artifact that should ship with the repo) and update
    `groot/config.py`'s `WAKEWORD_MODEL_FILE` to point there instead of
    `training/my_custom_model/hey_groot.onnx`.
  - TTS (voice output): explicitly deferred by user choice — not building this pass.
- Phases 4–7: not started.

## Future requirements (noted now, built later)

- **Phase 4/5 — professional skills for Groot.** User wants Groot itself equipped with
  skills/capabilities for web dev, UI/UX, frontend, and backend work — not just raw chat.
  This only makes sense once Groot has tool access (Phase 4) and can plan/execute multi-step
  tasks (Phase 5). Don't install anything for this in Phase 1–3. When Phase 4/5 starts,
  design how Groot selects and invokes these capabilities (likely: a tool/skill registry
  it can call into, gated by the same permission system as file/command access). User's
  laptop OS is Ubuntu (26.04) — these skills should target Linux/Ubuntu specifically
  (command syntax, package manager assumptions, paths), not be OS-agnostic/generic.

- **Phase 7 (or earlier) — Android support.** User wants Groot usable from Android, not
  just PC. Architecture undecided: could be phone-as-remote-client (PC keeps running the
  model, phone talks to it over local network — light, works on any phone) or fully
  standalone on-device inference (via Termux + community Ollama/llama.cpp build — heavier,
  no official Ollama Android app exists). User deferred the decision — revisit at latest by
  Phase 7 (Portability), but keep it in mind earlier too: e.g. Phase 4's tool/permission
  model and Phase 2's memory storage should not assume single-machine-only if avoidable.

- **Phase 3 — voice activation, speaker-locked, always-on at boot.** User wants Groot
  voice-triggered (wake word, not manual launch every time) AND gated so it only activates
  on *the user's* voice specifically — not anyone else's. This is beyond the roadmap's
  original Phase 3 scope (which only mentioned optional TTS for output). Needs two offline
  local pieces: a wake-word/activation engine, and a speaker verification step (voiceprint
  match against an enrolled sample of the user) before Groot treats input as a real
  command. User also wants this always listening from laptop startup — i.e. the wake-word
  listener should run as a background service (systemd user service, same pattern as the
  Ollama service) that starts automatically at boot, not something launched manually each
  session. Must stay fully offline per the hard constraints above. Not started — build in
  Phase 3.

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
