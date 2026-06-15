"""Word timings -> styled ASS with per-word karaoke timing.

Two looks, both rendered by libass — which is exactly what Kdenlive feeds its
subtitles through (the MLT ``avfilter.subtitles`` filter), so they animate in
Kdenlive's preview and export as well as in mpv/ffmpeg burn-in:

- **sweep** — the classic ``\\kf`` wipe: one Dialogue event per line, the active
  word fills from the base colour to the highlight colour over its duration.
- **pop** — per-word highlight (the CapCut/karaoke look): one Dialogue event per
  *word window*. The whole line stays on screen; the currently-spoken word
  switches to the highlight colour while the rest sit in the base colour, so the
  highlight tracks the audio word by word. ``\\kf`` can't recolour-and-revert per
  word, so pop is built from per-word events instead.

Validate output in mpv before Kdenlive (PLAN Phase 2). ``generate_ass`` can also
emit the ``[Kdenlive Extradata]`` block (``kdenlive_extradata=True``) so the file
imports onto a native Kdenlive subtitle track with the style registered as the
layer default — Path A.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KaraokePreset(str, Enum):
    SWEEP = "sweep"   # classic fill/wipe over the active word
    POP = "pop"       # per-word highlight (colour switch, tracks the audio)


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    start: float  # seconds
    end: float    # seconds

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def ass_timestamp(seconds: float) -> str:
    """Seconds -> ASS ``H:MM:SS.cs`` (centisecond precision)."""
    if seconds < 0:
        seconds = 0.0
    total_cs = round(seconds * 100)
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _cs(duration_seconds: float) -> int:
    """Duration in centiseconds, the unit ASS ``\\k``/``\\kf`` expects. Min 1."""
    return max(1, round(duration_seconds * 100))


def group_lines(
    words: list[Word],
    max_chars: int = 32,
    max_words: int = 7,
) -> list[list[Word]]:
    """Group words into caption lines, mirroring subtitle line-break behaviour.

    Breaks when adding the next word would exceed ``max_chars`` or ``max_words``.
    """
    lines: list[list[Word]] = []
    current: list[Word] = []
    char_count = 0
    for w in words:
        added = len(w.text) + (1 if current else 0)
        if current and (len(current) >= max_words or char_count + added > max_chars):
            lines.append(current)
            current, char_count = [], 0
            added = len(w.text)
        current.append(w)
        char_count += added
    if current:
        lines.append(current)
    return lines


def _sweep_line_text(line: list[Word]) -> str:
    """Emit the ``{\\kf<cs>}word`` run for one line.

    Gaps between consecutive words become a ``\\k`` hold on the joining space so
    the wipe timing stays locked to the audio.
    """
    parts: list[str] = []
    for i, w in enumerate(line):
        if i > 0:
            gap = line[i].start - line[i - 1].end
            if gap > 0.02:
                parts.append(f"{{\\k{_cs(gap)}}} ")
            else:
                parts.append(" ")
        parts.append(f"{{\\kf{_cs(w.duration)}}}{w.text}")
    return "".join(parts)


def _pop_event_text(line: list[Word], active: int, style) -> str:
    """Full line text for a pop event with ``active`` word highlighted.

    Every word carries an explicit ``\\1c`` colour so state never bleeds from one
    word's override block into the next: the active word gets the highlight
    colour, the rest the base colour. Pure colour highlight — no scaling — so the
    line stays still and only the colour tracks the spoken word.
    """
    from ..styles.presets import ass_override_colour

    hl = ass_override_colour(style.highlight_rgb)
    base = ass_override_colour(style.base_rgb)
    parts: list[str] = []
    for k, w in enumerate(line):
        if k:
            parts.append(" ")
        colour = hl if k == active else base
        parts.append(f"{{\\1c{colour}}}{w.text}")
    return "".join(parts)


def _pop_events(line: list[Word], style) -> list[tuple[float, float, str]]:
    """One ``(start, end, text)`` per word: the whole line shown, one word lit.

    A word's highlight holds until the next word starts (so silences between
    words don't drop the caption), and the last word holds to its own end.
    """
    out: list[tuple[float, float, str]] = []
    n = len(line)
    for j in range(n):
        start = line[j].start
        end = line[j + 1].start if j < n - 1 else line[j].end
        if end <= start:
            end = start + 0.04  # ~1 frame floor; ASS/libass need end > start
        out.append((start, end, _pop_event_text(line, j, style)))
    return out


def _kdenlive_extradata(style_name: str, max_layer: int = 0) -> list[str]:
    """The ``[Kdenlive Extradata]`` block Kdenlive writes/reads for native tracks.

    Registers ``style_name`` as the default style for every layer so the import
    lands as a first-class Kdenlive subtitle track (Path A). libass ignores this
    section, so it's harmless for burn-in too.
    """
    default_styles = ",".join([style_name] * (max_layer + 1))
    return [
        "[Kdenlive Extradata]",
        f"MaxLayer: {max_layer}",
        f"DefaultStyles: {default_styles}",
        "",
    ]


def generate_ass(
    words: list[Word],
    style=None,
    preset: KaraokePreset | str = KaraokePreset.SWEEP,
    *,
    play_res: tuple[int, int] = (1920, 1080),
    max_chars: int = 32,
    max_words: int = 7,
    kdenlive_extradata: bool = False,
) -> str:
    """Render word timings to a complete ASS document string.

    ``kdenlive_extradata`` adds the ``[Kdenlive Extradata]`` block so the file
    imports onto a native Kdenlive subtitle track (Path A); leave it off for
    plain libass burn-in (Path B).
    """
    from ..styles import NULDRUMS  # local import keeps core import-light

    style = style or NULDRUMS
    preset = KaraokePreset(preset)

    width, height = play_res
    head = [
        "[Script Info]",
        "; Generated by NulCaption",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
    ]
    if kdenlive_extradata:
        head += _kdenlive_extradata(style.name)
    head += [
        "[V4+ Styles]",
        style.format_line(),
        style.to_ass_style_line(),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text",
    ]

    events: list[str] = []
    for line in group_lines(words, max_chars=max_chars, max_words=max_words):
        if not line:
            continue
        if preset is KaraokePreset.POP:
            for start_s, end_s, text in _pop_events(line, style):
                events.append(
                    f"Dialogue: 0,{ass_timestamp(start_s)},{ass_timestamp(end_s)},"
                    f"{style.name},,0,0,0,,{text}"
                )
        else:
            start = ass_timestamp(line[0].start)
            end = ass_timestamp(line[-1].end)
            text = _sweep_line_text(line)
            events.append(
                f"Dialogue: 0,{start},{end},{style.name},,0,0,0,,{text}"
            )

    return "\n".join(head + events) + "\n"
