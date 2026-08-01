"""Speaker enrollment and verification.

Gates whether audio that triggers the wake word is actually Groot's owner, versus
background noise or someone else's voice. Uses Resemblyzer to compute a voiceprint
(embedding) from a few enrollment recordings, then compares new utterances against
it via cosine similarity.
"""

from __future__ import annotations

import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav

from groot.config import PROJECT_ROOT

VOICEPRINT_FILE = PROJECT_ROOT / "voiceprint.npy"
DEFAULT_THRESHOLD = 0.4

_encoder: VoiceEncoder | None = None


def _get_encoder() -> VoiceEncoder:
    global _encoder
    if _encoder is None:
        _encoder = VoiceEncoder()
    return _encoder


def is_enrolled() -> bool:
    return VOICEPRINT_FILE.exists()


def enroll_from_wavs(wav_paths: list[str]) -> None:
    """Compute and save a voiceprint averaged over one or more recordings."""
    encoder = _get_encoder()
    embeds = [encoder.embed_utterance(preprocess_wav(path)) for path in wav_paths]
    voiceprint = np.mean(embeds, axis=0)
    np.save(VOICEPRINT_FILE, voiceprint)


def enroll_from_audio(clips: list[np.ndarray], sample_rate: int) -> None:
    """Compute and save a voiceprint averaged over one or more in-memory recordings."""
    encoder = _get_encoder()
    embeds = [
        encoder.embed_utterance(preprocess_wav(clip, source_sr=sample_rate)) for clip in clips
    ]
    voiceprint = np.mean(embeds, axis=0)
    np.save(VOICEPRINT_FILE, voiceprint)


def similarity_score(clip: np.ndarray, sample_rate: int) -> float:
    """Cosine similarity between the given audio and the enrolled voiceprint."""
    if not is_enrolled():
        raise RuntimeError("No voiceprint enrolled yet - run `python -m groot.cli enroll` first.")
    voiceprint = np.load(VOICEPRINT_FILE)
    encoder = _get_encoder()
    embed = encoder.embed_utterance(preprocess_wav(clip, source_sr=sample_rate))
    return float(np.dot(voiceprint, embed) / (np.linalg.norm(voiceprint) * np.linalg.norm(embed)))


def verify_audio(clip: np.ndarray, sample_rate: int, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """Return True if the given audio matches the enrolled voiceprint closely enough."""
    return similarity_score(clip, sample_rate) >= threshold
