"""Client for the system-wide STT service (whisper-server / parakeet).

NulCaption prefers a shared, already-warm speech-to-text daemon when one is
running, instead of cold-loading its own whisper.cpp model on every caption job.
The daemon is the ``whispermodel`` service (``~/programming/Models/whispermodel``):
a whisper.cpp ``whisper-server`` holding large-v3-turbo warm on the GPU, reachable
at ``http://127.0.0.1:48450/inference``. It is planned to be swapped for a
Parakeet backend behind the **same** ``POST /inference`` multipart contract, so
this client targets that HTTP contract, not whisper specifically — when the
engine changes, captioning follows it with no code change here.

We post 16 kHz mono WAV and request ``verbose_json``, which carries per-word
``start``/``end`` timestamps in ``segments[].words[]`` — the word timing karaoke
needs. Endpoint resolution follows the repo-wide convention: ``$WHISPER_HTTP_URL``
(default ``http://127.0.0.1:48450/inference``).

Dependency-free: stdlib ``urllib`` only (nulcaption ships no third-party deps).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from ..ass import Word

DEFAULT_SERVICE_URL = "http://127.0.0.1:48450/inference"


class ServiceError(RuntimeError):
    """The STT service was unreachable or returned unusable output.

    Raised so :func:`nulcaption.transcribe.transcribe` can fall back to the
    local whisper-cli backend. A *successful* response that simply contains no
    speech is **not** an error — it returns an empty word list.
    """


def service_url(override: str | None = None) -> str:
    """Resolve the ``/inference`` endpoint.

    Priority: explicit ``override`` > ``$WHISPER_HTTP_URL`` > the default
    ``http://127.0.0.1:48450/inference``. ``$WHISPER_HTTP_URL`` is the same env
    var the other ``whispermodel`` clients (``voicechat`` et al.) honour.
    """
    return override or os.environ.get("WHISPER_HTTP_URL") or DEFAULT_SERVICE_URL


def _is_punct(text: str) -> bool:
    """True for a token with no alphanumerics (e.g. ``","``, ``"."``)."""
    return bool(text) and not any(ch.isalnum() for ch in text)


def _parse_verbose_json(data: dict, *, max_word_dur: float) -> list[Word]:
    """Flatten ``segments[].words[]`` (verbose_json) to ``[Word]``.

    Punctuation-only tokens come back as their own word entries with timing that
    stretches across a following pause; merge them onto the preceding word and
    keep that word's real end so a caption reads ``"country."`` (not ``"country"``
    ``+`` ``"."``) and doesn't hang on screen. Word durations are clamped to
    ``max_word_dur`` for the same reason the local backend clamps them.
    """
    words: list[Word] = []
    for seg in data.get("segments", []):
        for w in seg.get("words") or []:
            text = (w.get("word") or "").strip()
            if not text:
                continue
            start = float(w.get("start", 0.0))
            end = float(w.get("end", start))
            if end < start:
                end = start
            if _is_punct(text) and words:
                prev = words[-1]
                words[-1] = Word(prev.text + text, prev.start, prev.end)
                continue
            if end - start > max_word_dur:
                end = start + max_word_dur
            words.append(Word(text=text, start=start, end=end))
    return words


def _multipart(fields: dict[str, str], wav: Path) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body (text fields + the WAV file)."""
    boundary = f"----nulcaption{uuid.uuid4().hex}"
    nl = "\r\n"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (f"--{boundary}{nl}"
             f'Content-Disposition: form-data; name="{name}"{nl}{nl}'
             f"{value}{nl}").encode()
        )
    parts.append(
        (f"--{boundary}{nl}"
         f'Content-Disposition: form-data; name="file"; filename="{wav.name}"{nl}'
         f"Content-Type: audio/wav{nl}{nl}").encode()
    )
    parts.append(wav.read_bytes())
    parts.append(f"{nl}--{boundary}--{nl}".encode())
    return b"".join(parts), boundary


def transcribe_via_service(
    wav: Path,
    *,
    base_url: str,
    language: str = "auto",
    max_word_dur: float = 2.0,
    timeout: float = 600.0,
) -> list[Word]:
    """POST ``wav`` to the STT service and return normalised word timings.

    Raises :class:`ServiceError` when the service is unreachable, returns a
    non-2xx / non-JSON response, or returns text **without** per-word
    timestamps (a backend that can't drive karaoke — the caller should fall
    back to the local whisper-cli). Returns ``[]`` only when the service
    reports no speech at all.
    """
    fields = {
        "response_format": "verbose_json",
        "max_len": "1",          # whisper-server: one word per segment
        "split_on_word": "true",
    }
    if language and language != "auto":
        fields["language"] = language
    body, boundary = _multipart(fields, wav)
    req = urllib.request.Request(
        base_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.URLError, OSError) as exc:
        raise ServiceError(f"STT service unreachable at {base_url}: {exc}") from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ServiceError(f"STT service returned non-JSON from {base_url}: {exc}") from exc

    words = _parse_verbose_json(data, max_word_dur=max_word_dur)
    if words:
        return words
    # No per-word timings parsed. If the service still produced text, it's a
    # backend that doesn't emit word timestamps (useless for karaoke) -> signal
    # a fallback. No text either means genuine silence -> an honest empty result.
    if (data.get("text") or "").strip():
        raise ServiceError(
            f"STT service at {base_url} returned text without word timestamps "
            "(cannot drive karaoke timing)"
        )
    return []
