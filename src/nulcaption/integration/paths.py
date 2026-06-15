"""Two integration paths.

Phase 0 is resolved (confirmed against the fork's source): Kdenlive renders
subtitles through MLT's ``avfilter.subtitles`` filter — i.e. **libass** — so it
animates ``\\k``/``\\kf`` karaoke in both preview and export, and its ASS
importer preserves inline override tags and custom ``[V4+ Styles]`` verbatim. So
**both** paths are viable:

- **Path A — native subtitle track (editable).** Hand Kdenlive's built-in
  subtitle importer a Kdenlive-native ``.ass``. It lands on a real subtitle
  track, stays editable, and is saved in the project. :func:`apply_native_track`
  prepares that file. In the fork, the embedded "Auto Karaoke Captions" panel
  triggers the import over the D-Bus bridge; outside it, the user imports the
  prepared file via *Subtitles → Import Subtitle File*.
- **Path B — burn-in via ffmpeg/libass (guaranteed).** :func:`burn_in`. Same
  libass renderer, baked into pixels — the dependable final-render path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _first_style_name(ass_text: str) -> str | None:
    """Return the first ``[V4+ Styles]`` style name, or ``None`` if absent."""
    for line in ass_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Style:"):
            return stripped[len("Style:"):].strip().split(",", 1)[0].strip()
    return None


def _ensure_kdenlive_native(ass_text: str) -> str:
    """Insert the ``[Kdenlive Extradata]`` block if it isn't already present.

    Kdenlive writes this block (``MaxLayer`` + ``DefaultStyles``) for its native
    tracks and reads it back on import to assign each layer's default style.
    Files from :func:`nulcaption.ass.generate_ass` with ``kdenlive_extradata=True``
    already have it; this makes any other libass ASS import cleanly too. The
    block goes right before ``[V4+ Styles]`` (where Kdenlive emits it).
    """
    if "[Kdenlive Extradata]" in ass_text:
        return ass_text
    style = _first_style_name(ass_text) or "Default"
    block = f"[Kdenlive Extradata]\nMaxLayer: 0\nDefaultStyles: {style}\n\n"
    marker = "[V4+ Styles]"
    idx = ass_text.find(marker)
    if idx == -1:
        # No styles section to anchor to; prepend so Kdenlive still finds it.
        return block + ass_text
    return ass_text[:idx] + block + ass_text[idx:]


def apply_native_track(ass_path: str | Path, *, out: str | Path | None = None) -> Path:
    """Path A: prepare a Kdenlive-native ``.ass`` for a native subtitle track.

    Reads ``ass_path``, ensures it carries the ``[Kdenlive Extradata]`` block, and
    writes a Kdenlive-native sibling (default: ``<name>.kdenlive.ass``). The
    karaoke override tags and the custom style survive Kdenlive's importer
    unchanged (verified against ``SubtitleModel::importSubtitle``), so the track
    renders the same per-word highlight as burn-in.

    Returns the path to the import-ready file. The actual import into a running
    instance is Kdenlive's built-in *Import Subtitle File* action (driven by the
    fork's embedded panel over D-Bus in the product UX).
    """
    ass_path = Path(ass_path)
    text = ass_path.read_text(encoding="utf-8")
    native = _ensure_kdenlive_native(text)
    out_path = Path(out) if out else ass_path.with_suffix(".kdenlive.ass")
    out_path.write_text(native, encoding="utf-8")
    return out_path


def burn_in(
    video_in: str | Path,
    ass_path: str | Path,
    video_out: str | Path,
    *,
    crf: int = 18,
    preset: str = "medium",
) -> Path:
    """Path B: burn an ASS subtitle (with karaoke) into a video via ffmpeg/libass.

    The ``subtitles`` filter is fussy about Windows paths (drive colons), so we
    run ffmpeg with the working directory set to the ASS file's folder and pass
    only its filename to the filter.
    """
    ass_path = Path(ass_path).resolve()
    video_in = Path(video_in).resolve()
    video_out = Path(video_out).resolve()

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-vf", f"subtitles={ass_path.name}",
        "-c:a", "copy",
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        str(video_out),
    ]
    subprocess.run(cmd, cwd=str(ass_path.parent), check=True)
    return video_out
