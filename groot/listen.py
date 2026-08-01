"""Always-on wake-word + speaker-verified voice listener.

Continuously listens for "hey groot" via a custom-trained openWakeWord model,
verifies the speaker against the enrolled voiceprint (so it only responds to
its owner), transcribes the command via faster-whisper, then feeds the text
through the same conversation pipeline as `groot chat`.

Uses rolling sd.rec() blocks rather than a persistent sd.InputStream - on this
hardware/driver combo, InputStream delivered audio that consistently scored
~0 even for real "hey groot" utterances that scored correctly (~0.2+) when
captured via a single continuous sd.rec() call sliced into chunks afterward.
Each POLL_BLOCK_SECONDS block is recorded whole (continuous, matching the
proven-working pattern) then sliced into model-sized chunks in software -
only the brief gap *between* blocks (while sd.rec() restarts) is a risk, not
gaps within a block, so the block is sized to comfortably fit one utterance.
"""

from __future__ import annotations

import time

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from rich.console import Console

from groot import speaker, stt, tts
from groot.audio_io import SAMPLE_RATE
from groot.config import WAKEWORD_MODEL_FILE, load_config
from groot.conversation import GrootSession
from groot.ollama_client import OllamaError

console = Console()

CHUNK_SIZE = 1280  # 80ms at 16kHz — openWakeWord's expected feed size
POLL_BLOCK_SECONDS = 1.6  # recorded as one continuous block, then sliced into chunks
WAKEWORD_THRESHOLD = 0.08
COMMAND_SECONDS = 5.0  # how long to record the command after the wake word triggers
POST_TRIGGER_DISCARD_SECONDS = 0.5  # absorb trailing "...groot" audio before recording the command


def listen() -> None:
    config = load_config()

    if not WAKEWORD_MODEL_FILE.exists():
        console.print(f"[red]No wake-word model found at {WAKEWORD_MODEL_FILE}.[/red]")
        raise SystemExit(1)
    if not speaker.is_enrolled():
        console.print(
            "[red]No voiceprint enrolled.[/red] Run [bold]python -m groot.cli enroll[/bold] first."
        )
        raise SystemExit(1)

    oww_model = Model(wakeword_model_paths=[str(WAKEWORD_MODEL_FILE)])
    wakeword_name = next(iter(oww_model.models.keys()))
    session = GrootSession(config)

    console.print('[bold cyan]Groot[/bold cyan] is listening for "Hey Groot"... (Ctrl+C to stop)')

    try:
        while True:
            time.sleep(0.3)  # let the audio device settle between rapid sd.rec() cycles
            block = _record_int16(POLL_BLOCK_SECONDS)
            block_max = 0.0
            triggered = False
            for i in range(0, len(block) - CHUNK_SIZE, CHUNK_SIZE):
                prediction = oww_model.predict(block[i:i + CHUNK_SIZE])
                block_max = max(block_max, prediction.get(wakeword_name, 0.0))
                if prediction.get(wakeword_name, 0.0) > WAKEWORD_THRESHOLD:
                    triggered = True
                    break

            console.print(f"[dim]· block max score: {block_max:.3f}[/dim]")
            if not triggered:
                continue

            console.print("[dim]wake word detected...[/dim]")
            _record_seconds(POST_TRIGGER_DISCARD_SECONDS)  # absorb trailing wake-word audio
            console.print("[dim]listening for your command...[/dim]")
            command_audio = _record_seconds(COMMAND_SECONDS)

            try:
                score = speaker.similarity_score(command_audio, SAMPLE_RATE)
                console.print(f"[dim]speaker similarity: {score:.3f}[/dim]")
                if score < speaker.DEFAULT_THRESHOLD:
                    console.print("[yellow]Voice not recognized — ignoring.[/yellow]")
                    continue

                text = stt.transcribe(command_audio, config)
                if not text:
                    console.print("[yellow]Didn't catch that.[/yellow]")
                    continue

                console.print(f"[bold green]you[/bold green] > {text}")
                console.print("[bold magenta]groot[/bold magenta] > ", end="")
                reply = ""
                try:
                    for piece in session.turn(text):
                        console.print(piece, end="")
                        reply += piece
                except OllamaError as e:
                    console.print(f"\n[red]{e}[/red]")
                    continue
                console.print()
                tts.speak(reply)
            finally:
                # A full turn involves several seconds of speaker verification, STT, and
                # an LLM call - the audio device needs more than the usual inter-poll
                # settle time to recover cleanly afterward, and the wake-word model's
                # internal buffer should start fresh rather than carry stale state.
                oww_model.reset()
                time.sleep(1.0)
    except KeyboardInterrupt:
        console.print("\n[dim]bye.[/dim]")


def _record_int16(duration: float) -> np.ndarray:
    """Blocking-record `duration` seconds as a flat int16 array."""
    n_samples = max(1, int(duration * SAMPLE_RATE))
    audio = sd.rec(n_samples, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return audio.flatten()


def _record_seconds(duration: float) -> np.ndarray:
    """Blocking-record `duration` seconds as flat float32 in [-1, 1]."""
    return _record_int16(duration).astype(np.float32) / 32768.0
