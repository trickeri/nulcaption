"""Transcription frontend: ffmpeg audio extract -> whisper.cpp (Vulkan) words.

The default (and only fully-wired) backend is **whisper.cpp with the Vulkan
GGML backend**, driven via the ``whisper-cli`` binary provisioned by
:mod:`nulcaption.setup`. Word-level timestamps come from ``--max-len 1
--split-on-word`` so each emitted segment is a single word with start/end
offsets — the form the ASS karaoke generator needs.

Output is normalised to :class:`nulcaption.ass.Word` so the generator never sees
backend-specific shapes.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from enum import Enum
from pathlib import Path

from .. import runtime as rt
from ..ass import Word


class TranscribeBackend(str, Enum):
    WHISPER_CPP_VULKAN = "whisper-cpp-vulkan"  # default, fully implemented
    WHISPERX = "whisperx"                      # alt (forced alignment) — Phase 1
    FASTER_WHISPER = "faster-whisper"          # alt (CTranslate2) — Phase 1


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


def _looks_like_wav_16k_mono(path: Path) -> bool:
    return path.suffix.lower() == ".wav"


def _parse_whisper_json(data: dict) -> list[Word]:
    """Normalise whisper.cpp ``-oj`` output to ``[Word]`` (offsets are ms)."""
    words: list[Word] = []
    for seg in data.get("transcription", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        off = seg.get("offsets") or {}
        start = float(off.get("from", 0)) / 1000.0
        end = float(off.get("to", 0)) / 1000.0
        if end < start:
            end = start
        words.append(Word(text=text, start=start, end=end))
    return words


def transcribe(
    audio_path: str | Path,
    backend: TranscribeBackend | str = TranscribeBackend.WHISPER_CPP_VULKAN,
    *,
    language: str = "auto",
    threads: int | None = None,
) -> list[Word]:
    """Return normalised word timings for ``audio_path``.

    ``audio_path`` may be any media ffmpeg can read; non-WAV inputs are extracted
    to mono 16 kHz first.
    """
    backend = TranscribeBackend(backend)
    if backend is not TranscribeBackend.WHISPER_CPP_VULKAN:
        raise NotImplementedError(
            f"{backend.value} is a Phase 1 alternative; use whisper-cpp-vulkan"
        )

    rt.require_ready()
    src = Path(audio_path)

    with tempfile.TemporaryDirectory(prefix="nulcaption-") as td:
        tmp = Path(td)
        wav = src if _looks_like_wav_16k_mono(src) else extract_audio(src, tmp / "audio.wav")
        out_base = tmp / "out"

        cmd = [
            str(rt.whisper_bin()),
            "-m", str(rt.model_path()),
            "-f", str(wav),
            "--max-len", "1",        # one word per segment
            "--split-on-word",
            "--output-json", "--output-file", str(out_base),
            "--language", language,
            "--no-prints",
        ]
        if threads:
            cmd += ["--threads", str(threads)]

        subprocess.run(cmd, check=True)
        data = json.loads((out_base.with_suffix(".json")).read_text(encoding="utf-8"))

    return _parse_whisper_json(data)
