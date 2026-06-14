"""Transcription frontend: ffmpeg audio extract -> Whisper word timestamps.

Backend choice is a Phase 0 decision driven by *word-boundary quality* (the #1
thing that makes karaoke look amateur), not raw WER:

- ``whisperx``       — forced alignment, tightest boundaries (safe default).
- ``faster-whisper`` — ``word_timestamps=True``, fast (CTranslate2/CUDA).
- ``whisper.cpp``    — token timestamps + Vulkan (vendor-neutral).

Output is normalised to :class:`nulcaption.ass.Word` so the generator never sees
backend-specific shapes.
"""
from __future__ import annotations

import subprocess
from enum import Enum
from pathlib import Path

from ..ass import Word


class TranscribeBackend(str, Enum):
    WHISPERX = "whisperx"
    FASTER_WHISPER = "faster-whisper"
    WHISPER_CPP = "whisper-cpp"


def extract_audio(src: str | Path, dst: str | Path) -> Path:
    """Extract mono 16 kHz PCM WAV via ffmpeg (the form ASR backends expect)."""
    dst = Path(dst)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
         "-vn", str(dst)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return dst


def transcribe(
    audio_path: str | Path,
    backend: TranscribeBackend | str = TranscribeBackend.WHISPERX,
    *,
    device: str = "cuda",
) -> list[Word]:
    """Return normalised word timings.

    TODO(phase-1): dispatch to the chosen backend, request word timestamps, and
    normalise to ``Word(text, start, end)``. Handle the known edge cases:
    numbers-only words (whisperX sometimes drops their timestamps — approximate),
    overlapping/zero-length words, very long words.
    """
    raise NotImplementedError(
        f"Phase 1: implement {TranscribeBackend(backend).value} word-timestamp path"
    )
