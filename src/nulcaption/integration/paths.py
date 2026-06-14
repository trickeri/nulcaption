"""Two integration paths (PLAN decides which is primary in Phase 0).

- **Path A — native subtitle track (editable).** Import the ``.ass`` onto a
  Kdenlive subtitle track via the fork's D-Bus interface. Needs the running
  Linux fork — Phase 3.
- **Path B — burn-in via ffmpeg/libass (guaranteed).** Implemented and works on
  Windows now; libass honours ``\\k``/``\\kf`` karaoke timing reliably.
"""
from __future__ import annotations

import subprocess
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
