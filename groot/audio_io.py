"""Shared microphone capture helpers for enrollment and the wake-word listener."""

from __future__ import annotations

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


def record_seconds(duration: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Record `duration` seconds of mono audio from the default input device."""
    audio = sd.rec(
        int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32"
    )
    sd.wait()
    return audio.flatten()
