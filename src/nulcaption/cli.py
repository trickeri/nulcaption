"""End-to-end NulCaption CLI: media -> word timings -> karaoke ASS [-> burn-in].

Designed to be driven non-interactively (e.g. by an agent or the Kdenlive fork's
"Generate Captions" action). Stable contract: it reads any ffmpeg media, writes a
karaoke ``.ass``, and returns 0 on success / 1 no speech / 2 bad input / 3 backend
not provisioned. The fork passes ``--ass <tmp> --native`` and imports the result.

Examples
--------
Generate an editable ``.ass`` next to the input::

    nulcaption caption clip.mp4

Kdenlive-native track ASS at a chosen path (what the fork action runs)::

    nulcaption caption clip.mp4 --native --ass /tmp/clip.karaoke.ass

Burn the karaoke into a new video (Path B)::

    nulcaption caption clip.mp4 --burn -o clip.karaoke.mp4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config as cfgmod
from .ass import generate_ass
from .integration import burn_in
from .styles import all_presets
from .transcribe import transcribe


def _caption(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.is_file():
        print(f"error: no such file: {src}", file=sys.stderr)
        return 2

    # A named --style preset overrides the saved config; otherwise the config's
    # resolved appearance (what the settings window writes) is used.
    style = all_presets()[args.style] if args.style else args.config.to_style()
    print(f"[1/3] transcribing {src.name} (whisper.cpp Vulkan, large-v3-turbo)...")
    try:
        words = transcribe(
            src,
            language=args.language,
            use_vad=not args.no_vad,
            vad_threshold=args.vad_threshold,
        )
    except RuntimeError as e:  # backend not provisioned (run nulcaption-setup)
        print(f"error: {e}", file=sys.stderr)
        return 3
    print(f"      {len(words)} words")
    if not words:
        print("error: no speech recognised", file=sys.stderr)
        return 1

    ass_path = Path(args.ass) if args.ass else src.with_suffix(".ass")
    print(f"[2/3] generating {args.preset} karaoke ASS ({style.name} style)...")
    ass_path.write_text(
        generate_ass(
            words, style=style, preset=args.preset, kdenlive_extradata=args.native,
            max_words=args.max_words, max_chars=args.max_chars,
        ),
        encoding="utf-8",
    )
    print(f"      wrote {ass_path}")

    if args.burn:
        out = Path(args.output) if args.output else src.with_name(src.stem + ".karaoke.mp4")
        print(f"[3/3] burning in -> {out.name} ...")
        burn_in(src, ass_path, out)
        print(f"      wrote {out}")
    elif args.native:
        print("[3/3] Path A: import-ready for a Kdenlive subtitle track")
        print(f"      Subtitles -> Import Subtitle File: {ass_path}")
    else:
        print("[3/3] skipped burn-in (pass --burn to render a video, "
              "--native for a Kdenlive subtitle track)")
    return 0


def _restyle(args: argparse.Namespace) -> int:
    from .ass.restyle import restyle_ass_text

    src = Path(args.input)
    if not src.is_file():
        print(f"error: no such file: {src}", file=sys.stderr)
        return 2
    style = all_presets()[args.style] if args.style else args.config.to_style()
    try:
        text = src.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {src}: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else src
    out.write_text(restyle_ass_text(text, style), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nulcaption", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # Saved settings (settings window) become the defaults; explicit flags win.
    cfg = cfgmod.load()
    preset_names = sorted(all_presets())

    cap = sub.add_parser("caption", help="caption a media file")
    cap.add_argument("input", help="input media (any ffmpeg-readable file)")
    cap.add_argument("-o", "--output", help="output video path (with --burn)")
    cap.add_argument("--ass", help="output .ass path (default: alongside input)")
    cap.add_argument("--style", choices=preset_names, default=None,
                     help="use a named style preset instead of the "
                          "saved appearance settings")
    cap.add_argument("--preset", choices=["sweep", "pop"], default=cfg.preset)
    cap.add_argument("--language", default=cfg.language)
    cap.add_argument("--max-words", type=int, default=cfg.max_words)
    cap.add_argument("--max-chars", type=int, default=cfg.max_chars)
    cap.add_argument("--no-vad", action="store_true", default=not cfg.vad,
                     help="disable Silero VAD (VAD keeps captions off silence and "
                          "anchors word timings)")
    cap.add_argument("--vad-threshold", type=float, default=cfg.vad_threshold,
                     help="VAD speech-probability cutoff (whisper default 0.5). "
                          "Raise (0.6-0.7) for loud mixed tracks, lower for a "
                          "clean quiet mic track.")
    cap.add_argument("--burn", action="store_true", help="burn karaoke into a video")
    cap.add_argument("--native", action="store_true",
                     help="emit a Kdenlive-native .ass for a subtitle track (Path A)")
    cap.set_defaults(func=_caption, config=cfg)

    res = sub.add_parser("restyle",
                         help="restyle/reposition an existing .ass in place (no transcription)")
    res.add_argument("input", help="existing karaoke .ass file")
    res.add_argument("--out", help="output path (default: overwrite the input)")
    res.add_argument("--style", choices=preset_names, default=None,
                     help="use a named preset instead of the saved settings")
    res.set_defaults(func=_restyle, config=cfg)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
