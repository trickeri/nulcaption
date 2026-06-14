"""End-to-end NulCaption CLI: media -> word timings -> karaoke ASS [-> burn-in].

Examples
--------
Generate an editable ``.ass`` next to the input::

    nulcaption caption clip.mp4

Burn the karaoke into a new video (Path B)::

    nulcaption caption clip.mp4 --burn -o clip.karaoke.mp4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ass import generate_ass
from .integration import burn_in
from .styles import PRESETS
from .transcribe import transcribe


def _caption(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"error: no such file: {src}", file=sys.stderr)
        return 2

    style = PRESETS[args.style]
    print(f"[1/3] transcribing {src.name} (whisper.cpp Vulkan, large-v3)...")
    words = transcribe(src, language=args.language)
    print(f"      {len(words)} words")
    if not words:
        print("error: no speech recognised", file=sys.stderr)
        return 1

    ass_path = Path(args.ass) if args.ass else src.with_suffix(".ass")
    print(f"[2/3] generating {args.preset} karaoke ASS ({style.name} style)...")
    ass_path.write_text(
        generate_ass(words, style=style, preset=args.preset), encoding="utf-8"
    )
    print(f"      wrote {ass_path}")

    if args.burn:
        out = Path(args.output) if args.output else src.with_name(src.stem + ".karaoke.mp4")
        print(f"[3/3] burning in -> {out.name} ...")
        burn_in(src, ass_path, out)
        print(f"      wrote {out}")
    else:
        print("[3/3] skipped burn-in (pass --burn to render a video)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nulcaption", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("caption", help="caption a media file")
    cap.add_argument("input", help="input media (any ffmpeg-readable file)")
    cap.add_argument("-o", "--output", help="output video path (with --burn)")
    cap.add_argument("--ass", help="output .ass path (default: alongside input)")
    cap.add_argument("--style", choices=sorted(PRESETS), default="nuldrums")
    cap.add_argument("--preset", choices=["sweep", "pop"], default="sweep")
    cap.add_argument("--language", default="auto")
    cap.add_argument("--burn", action="store_true", help="burn karaoke into a video")
    cap.set_defaults(func=_caption)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
