"""Always-on wake-word + speaker-verified voice listener.

Continuously listens for "hey groot" via a custom-trained openWakeWord model,
verifies the speaker against the enrolled voiceprint (so it only responds to
its owner), transcribes the command via faster-whisper, then feeds the text
through the same conversation pipeline as `groot chat`.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from rich.console import Console

from groot import speaker, stt
from groot.audio_io import SAMPLE_RATE
from groot.config import WAKEWORD_MODEL_FILE, load_config
from groot.conversation import GrootSession
from groot.ollama_client import OllamaError

console = Console()

CHUNK_SIZE = 1280  # 80ms at 16kHz — openWakeWord's expected feed size
WAKEWORD_THRESHOLD = 0.5
COMMAND_SECONDS = 5.0  # how long to record the command after the wake word triggers


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

    oww_model = Model(wakeword_models=[str(WAKEWORD_MODEL_FILE)], inference_framework="onnx")
    wakeword_name = next(iter(oww_model.models.keys()))
    session = GrootSession(config)

    console.print('[bold cyan]Groot[/bold cyan] is listening for "Hey Groot"... (Ctrl+C to stop)')

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK_SIZE) as stream:
        try:
            while True:
                chunk, _ = stream.read(CHUNK_SIZE)
                prediction = oww_model.predict(chunk.flatten())

                if prediction.get(wakeword_name, 0.0) <= WAKEWORD_THRESHOLD:
                    continue

                console.print("[dim]wake word detected, listening for your command...[/dim]")
                command_audio = _record_seconds(COMMAND_SECONDS, stream)

                if not speaker.verify_audio(command_audio, SAMPLE_RATE):
                    console.print("[yellow]Voice not recognized — ignoring.[/yellow]")
                    continue

                text = stt.transcribe(command_audio, config)
                if not text:
                    console.print("[yellow]Didn't catch that.[/yellow]")
                    continue

                console.print(f"[bold green]you[/bold green] > {text}")
                console.print("[bold magenta]groot[/bold magenta] > ", end="")
                try:
                    for piece in session.turn(text):
                        console.print(piece, end="")
                except OllamaError as e:
                    console.print(f"\n[red]{e}[/red]")
                    continue
                console.print()
        except KeyboardInterrupt:
            console.print("\n[dim]bye.[/dim]")


def _record_seconds(duration: float, stream: sd.InputStream) -> np.ndarray:
    """Read `duration` seconds from an already-open int16 InputStream as float32."""
    n_chunks = int(duration * SAMPLE_RATE / CHUNK_SIZE)
    chunks = [stream.read(CHUNK_SIZE)[0] for _ in range(n_chunks)]
    audio_int16 = np.concatenate(chunks).flatten()
    return (audio_int16.astype(np.float32) / 32768.0)
