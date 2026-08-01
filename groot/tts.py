"""Text-to-speech via Piper - runs fully offline, no network calls."""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from piper import PiperVoice

from groot.config import PROJECT_ROOT

VOICE_MODEL = PROJECT_ROOT / "models" / "voices" / "en_GB-alan-medium.onnx"
VOICE_CONFIG = PROJECT_ROOT / "models" / "voices" / "en_GB-alan-medium.onnx.json"

_voice: PiperVoice | None = None


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(str(VOICE_MODEL), str(VOICE_CONFIG))
    return _voice


def speak(text: str) -> None:
    """Synthesize and play text out loud, blocking until playback finishes.

    Accumulates all synthesized chunks before playing as one clip rather than
    playing chunk-by-chunk - repeated sd.play() calls in quick succession hit
    the same audio-device settling issue as the wake-word listener's mic
    capture did, so a single playback call avoids that class of bug entirely.
    """
    if not text.strip():
        return
    voice = _get_voice()
    chunks = list(voice.synthesize(text))
    if not chunks:
        return
    audio = np.concatenate([c.audio_float_array for c in chunks])
    sd.play(audio, samplerate=chunks[0].sample_rate)
    sd.wait()
