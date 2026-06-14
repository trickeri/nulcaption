"""Two integration paths (PLAN decides which is primary in Phase 0).

- **Path A — native subtitle track (editable).** Import the ``.ass`` onto a
  Kdenlive subtitle track via the fork's D-Bus interface. Only viable if Phase 0
  confirms Kdenlive renders ``\\k``/``\\kf`` and doesn't strip tags on import.
- **Path B — burn-in via MLT/libass (guaranteed).** Apply the ASS as a filter in
  the render chain; libass honours karaoke timing reliably. Not editable after.

Recommended: support both — A for editing, B as the dependable final render.
"""
from __future__ import annotations

from pathlib import Path


def apply_native_track(ass_path: str | Path, *, track: int = 0) -> None:
    """Path A: import ASS onto a Kdenlive subtitle track over D-Bus.

    TODO(phase-3): call the fork's subtitle-import scripting method (shared
    bridge with NulEdit). Gated on the Phase 0 native-render decision.
    """
    raise NotImplementedError("Phase 3: native subtitle-track import (Path A)")


def burn_in(
    video_in: str | Path,
    ass_path: str | Path,
    video_out: str | Path,
) -> None:
    """Path B: burn subtitles in via MLT/ffmpeg libass.

    TODO(phase-3): drive the MLT ``avfilter.subtitles`` / ffmpeg ``ass`` filter
    using the MLT version bundled with the pinned Kdenlive (confirm exact filter
    name + params in Phase 0).
    """
    raise NotImplementedError("Phase 3: MLT/libass burn-in (Path B)")
