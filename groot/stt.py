"""Speech-to-text via faster-whisper - runs fully offline on CPU."""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

from groot.config import Config

_model: WhisperModel | None = None
_model_size: str | None = None


def _get_model(model_size: str) -> WhisperModel:
    global _model, _model_size
    if _model is None or _model_size != model_size:
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _model_size = model_size
    return _model


def transcribe(audio: np.ndarray, config: Config) -> str:
    """Transcribe 16kHz mono float32 audio to text."""
    model = _get_model(config.stt_model)
    segments, _ = model.transcribe(
        audio,
        language="en",
        beam_size=5,  # wider search than the default greedy decode - meaningfully more accurate, still fast on CPU for short clips
        vad_filter=True,  # trims leading/trailing silence and noise before transcribing, instead of feeding the whole raw window
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
