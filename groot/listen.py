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

After the wake word, a single trigger opens a whole CONVERSATION: commands
are recorded until you stop talking (silence-based, not a fixed window) and
Groot keeps listening for follow-ups without needing "Hey Groot" again,
until you go quiet for CONVERSATION_IDLE_SECONDS.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

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

# Silence-based command recording: keep recording until the user goes quiet,
# rather than a fixed window that cuts off longer commands mid-sentence.
SILENCE_SUBCHUNK_SECONDS = 0.5
SILENCE_RMS_THRESHOLD = 500  # observed quiet-room noise floor is ~500-1000
SILENCE_HANGOVER_SECONDS = 3.0  # stop after this much continuous quiet
MAX_RECORD_SECONDS = 25.0  # hard cap so a stuck mic can't record forever
POST_TRIGGER_DISCARD_SECONDS = 0.5  # absorb trailing "...groot" audio before recording the command

# After a command, keep listening for follow-ups without re-saying the wake
# word - if the user stays silent this long, fall back to wake-word polling.
CONVERSATION_IDLE_SECONDS = 12.0

SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# Set GROOT_DEBUG_AUDIO_DIR to dump every captured block to disk for offline inspection
DEBUG_DUMP_DIR = Path(os.environ["GROOT_DEBUG_AUDIO_DIR"]) if os.environ.get("GROOT_DEBUG_AUDIO_DIR") else None


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
    if DEBUG_DUMP_DIR is not None:
        console.print(f"[dim]debug audio dump: {DEBUG_DUMP_DIR}[/dim]")

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

            rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
            console.print(f"[dim]· RMS {rms:7.0f}  score: {block_max:.3f}[/dim]")
            if DEBUG_DUMP_DIR is not None:
                import scipy.io.wavfile as _wavfile
                DEBUG_DUMP_DIR.mkdir(exist_ok=True)
                _wavfile.write(str(DEBUG_DUMP_DIR / f"block_{int(time.time()*1000)}.wav"), SAMPLE_RATE, block)
            if not triggered:
                continue

            console.print("[dim]wake word detected...[/dim]")
            _record_seconds(POST_TRIGGER_DISCARD_SECONDS)  # absorb trailing wake-word audio

            try:
                # Conversation loop: keep handling commands without needing the wake
                # word again, until the user goes quiet for CONVERSATION_IDLE_SECONDS.
                while True:
                    console.print("[dim]listening for your command...[/dim]")
                    command_audio, spoke = _record_until_silence(CONVERSATION_IDLE_SECONDS)
                    if not spoke:
                        console.print("[dim]conversation idle, back to wake-word listening.[/dim]")
                        break

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
                    _speak_reply_as_it_streams(session, text)
                    console.print()
                    sd.stop()  # ensure the output stream is fully torn down before switching back to input
            except OllamaError as e:
                console.print(f"\n[red]{e}[/red]")
            finally:
                # After using the mic/speaker for a while, the wake-word model's
                # internal audio-feature preprocessor gets stuck (verified: mic RMS
                # keeps varying with real speech, but score stays frozen near 0 no
                # matter how long you wait or how many predict() calls happen).
                # Model.reset() only clears an unrelated prediction-smoothing
                # buffer, not the preprocessor's internal state, so it doesn't fix
                # this - recreate the model outright.
                oww_model = Model(wakeword_model_paths=[str(WAKEWORD_MODEL_FILE)])
                wakeword_name = next(iter(oww_model.models.keys()))
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[dim]bye.[/dim]")


def _speak_reply_as_it_streams(session: GrootSession, text: str) -> None:
    """Print + speak the reply sentence-by-sentence as it streams in, instead of
    waiting for the whole response before speaking (which felt sluggish/unsynced)."""
    buffer = ""
    for piece in session.turn(text):
        console.print(piece, end="")
        buffer += piece
        parts = SENTENCE_END_RE.split(buffer)
        for sentence in parts[:-1]:
            tts.speak(sentence)
        buffer = parts[-1]
    if buffer.strip():
        tts.speak(buffer)


def _record_int16(duration: float) -> np.ndarray:
    """Blocking-record `duration` seconds as a flat int16 array."""
    n_samples = max(1, int(duration * SAMPLE_RATE))
    audio = sd.rec(n_samples, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return audio.flatten()


def _record_seconds(duration: float) -> np.ndarray:
    """Blocking-record `duration` seconds as flat float32 in [-1, 1]."""
    return _record_int16(duration).astype(np.float32) / 32768.0


def _record_until_silence(max_wait_for_speech: float) -> tuple[np.ndarray, bool]:
    """Record until SILENCE_HANGOVER_SECONDS of quiet follows speech, or
    MAX_RECORD_SECONDS elapses. Returns (audio, spoke) - `spoke` is False if
    the user never made any sound above the noise floor within
    `max_wait_for_speech` (used to detect the end of a conversation)."""
    chunks: list[np.ndarray] = []
    silence_run = 0.0
    total = 0.0
    ever_spoke = False

    while total < MAX_RECORD_SECONDS:
        sub = _record_int16(SILENCE_SUBCHUNK_SECONDS)
        chunks.append(sub)
        total += SILENCE_SUBCHUNK_SECONDS
        rms = float(np.sqrt(np.mean(sub.astype(np.float64) ** 2)))

        if rms >= SILENCE_RMS_THRESHOLD:
            ever_spoke = True
            silence_run = 0.0
        else:
            silence_run += SILENCE_SUBCHUNK_SECONDS

        if ever_spoke and silence_run >= SILENCE_HANGOVER_SECONDS:
            break
        if not ever_spoke and total >= max_wait_for_speech:
            break

    audio_int16 = np.concatenate(chunks)
    return audio_int16.astype(np.float32) / 32768.0, ever_spoke
