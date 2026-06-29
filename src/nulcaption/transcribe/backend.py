"""Transcription frontend: ffmpeg audio extract -> whisper.cpp (Vulkan) words.

NulCaption supports **one** ASR backend on purpose: **whisper.cpp with the
Vulkan GGML backend**. Vulkan is the portable choice — it runs on NVIDIA, AMD,
and Intel GPUs, so anyone using the plugin gets GPU acceleration without a
vendor-specific (e.g. CUDA) toolchain. The binary is provisioned by
:mod:`nulcaption.setup` and driven via ``whisper-cli``.

Word-level timestamps come from ``--max-len 1 --split-on-word`` so each emitted
segment is a single word with start/end offsets — the form the ASS karaoke
generator needs. Output is normalised to :class:`nulcaption.ass.Word` so the
generator never sees backend-specific shapes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import runtime as rt
from ..ass import Word
from .service import ServiceError, transcribe_via_service
from .service import service_url as resolve_service_url


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


# whisper's word END timestamps are unreliable across a following pause: it
# stretches a word's end up to the next word's start, so a word before a silence
# can read as lasting many seconds. Left alone, that (a) makes a caption hang on
# screen across the quiet and (b) hides the gap from group_lines (which measures
# word.start - prev.end), so the line never breaks. Real spoken words almost
# never exceed this; clamp the end so the gap — and the silence — reappears.
MAX_WORD_DUR = 2.0  # seconds


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
        if end - start > MAX_WORD_DUR:
            end = start + MAX_WORD_DUR
        words.append(Word(text=text, start=start, end=end))
    return words


def transcribe(
    audio_path: str | Path,
    *,
    language: str = "auto",
    threads: int | None = None,
    use_vad: bool = True,
    vad_threshold: float | None = None,
    prefer_service: bool = True,
    service_url: str | None = None,
) -> list[Word]:
    """Return normalised word timings for ``audio_path``.

    ``audio_path`` may be any media ffmpeg can read; non-WAV inputs are extracted
    to mono 16 kHz first.

    Backend selection: when ``prefer_service`` is set (the default), the audio is
    sent to the shared system-wide STT daemon (``whispermodel`` / whisper-server,
    later Parakeet) if one is reachable — a model already warm in VRAM, so no
    per-job cold load. If that service is unreachable or can't supply word
    timestamps, we transparently fall back to the local whisper.cpp (Vulkan)
    backend. ``service_url`` overrides the endpoint (else ``$WHISPER_HTTP_URL``
    or the daemon default). A successful service response with no speech is
    trusted (returns ``[]``) — only an actual service *failure* falls back.

    ``use_vad`` (default on) only affects the **local** backend: it runs
    whisper's built-in Silero VAD so only detected speech is transcribed. This is
    what keeps captions off silent stretches and word timestamps locked to real
    speech — without it, whisper opens 30 s windows over silence and smears (or
    hallucinates, e.g. "how how how") words across the quiet. Falls back to
    no-VAD with a warning if the VAD model isn't provisioned. (The shared service
    runs its own VAD/engine config; a transducer backend like Parakeet does not
    hallucinate over silence, so this knob is moot there.)

    ``vad_threshold`` (whisper default 0.5) is the local-backend VAD
    speech-probability cutoff: raise it (e.g. 0.6–0.7) for clips with loud
    background audio bleeding into a mixed track so only confident speech is
    kept; lower it for a clean, quiet mic track. ``None`` leaves whisper's
    default.
    """
    src = Path(audio_path)

    with tempfile.TemporaryDirectory(prefix="nulcaption-") as td:
        tmp = Path(td)
        wav = src if _looks_like_wav_16k_mono(src) else extract_audio(src, tmp / "audio.wav")

        if prefer_service:
            url = resolve_service_url(service_url)
            try:
                words = transcribe_via_service(
                    wav, base_url=url, language=language, max_word_dur=MAX_WORD_DUR
                )
                print(f"[nulcaption] transcribed via shared STT service ({url})",
                      file=sys.stderr)
                return words
            except ServiceError as exc:
                print(f"[nulcaption] STT service unavailable ({exc}); "
                      "falling back to local whisper.cpp.", file=sys.stderr)

        # Local whisper.cpp (Vulkan) backend — self-contained, VAD-capable.
        rt.require_ready()
        out_base = tmp / "out"

        cmd = [
            str(rt.whisper_bin()),
            "-m", str(rt.model_path()),
            "-f", str(wav),
            "--max-len", "1",        # one word per segment
            "--split-on-word",
            "--suppress-nst",        # drop non-speech tokens (e.g. [music], noise)
            "--output-json", "--output-file", str(out_base),
            "--language", language,
            "--no-prints",
        ]
        if use_vad:
            if rt.vad_model_ready():
                cmd += [
                    "--vad",
                    "--vad-model", str(rt.vad_model_path()),
                    # pad detected speech so leading/trailing phonemes aren't clipped
                    "--vad-speech-pad-ms", "60",
                ]
                if vad_threshold is not None:
                    cmd += ["--vad-threshold", f"{vad_threshold:g}"]
            else:
                print(
                    "[nulcaption] VAD model not provisioned; transcribing without "
                    "VAD (captions may appear over silence). Run nulcaption-setup.",
                    file=sys.stderr,
                )
        if threads:
            cmd += ["--threads", str(threads)]

        subprocess.run(cmd, check=True, env=rt.whisper_env())
        data = json.loads((out_base.with_suffix(".json")).read_text(encoding="utf-8"))

    return _parse_whisper_json(data)
