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

import re
from dataclasses import dataclass
from enum import Enum

# A word ends a sentence if it ends in . ! or ? (allowing trailing quotes/brackets).
_SENTENCE_END = re.compile(r"""[.!?]["'”’)\]]*$""")


def _ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.rstrip()))


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
    max_chars: int = 42,
    max_words: int = 7,
    max_gap: float = 0.7,
) -> list[list[Word]]:
    """Group words into caption lines so captions track speech, not silence.

    A line is broken:

    - **after a sentence end** (a word ending in ``.``/``!``/``?``) — the next
      sentence starts a fresh caption;
    - **before a silence** longer than ``max_gap`` seconds — so no caption hangs
      on screen across a pause (the gap falls *between* captions, shown by
      neither);
    - when it would exceed ``max_words`` or ``max_chars`` — keeping captions in
      the readable ~4-7 word range.

    Because each caption spans only its own words' timing, breaking here is what
    keeps captions off of silent stretches.
    """
    lines: list[list[Word]] = []
    current: list[Word] = []
    char_count = 0
    for w in words:
        if current:
            gap = w.start - current[-1].end
            added = len(w.text) + 1
            if len(current) >= max_words or char_count + added > max_chars or gap > max_gap:
                lines.append(current)
                current, char_count = [], 0
        added = len(w.text) + (1 if current else 0)
        current.append(w)
        char_count += added
        if _ends_sentence(w.text):
            lines.append(current)
            current, char_count = [], 0
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


def _pop_events(
    line: list[Word], style, next_start: float | None = None
) -> list[tuple[float, float, str]]:
    """One ``(start, end, text)`` per word: the whole line shown, one word lit.

    A word's highlight holds until the next word starts (so silences between
    words don't drop the caption), and the last word holds to its own end —
    but never past ``next_start`` (the next line's first word). Whisper stretches
    a pre-pause word's end up to ``MAX_WORD_DUR``, so without this cap the last
    word of a line would linger on screen well into the following caption.
    """
    out: list[tuple[float, float, str]] = []
    n = len(line)
    for j in range(n):
        start = line[j].start
        end = line[j + 1].start if j < n - 1 else line[j].end
        if next_start is not None:
            end = min(end, next_start)
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
    max_chars: int = 42,
    max_words: int = 7,
    max_gap: float = 0.7,
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

    # libass ignores MarginV for middle alignment (4/5/6) — it always dead-centres
    # the text — so the GUI's Y margin would do nothing there. Position the line
    # explicitly with \pos instead: the margin offsets it above the frame centre
    # (positive = higher). Top/bottom keep using the style's MarginV, which works.
    mid_pos = ""
    if style.alignment in (4, 5, 6):
        cy = height // 2 - style.margin_v
        mid_pos = f"{{\\an{style.alignment}\\pos({width // 2},{cy})}}"

    prefix = mid_pos + style.event_overrides()  # \pos + {\xshad..\yshad..}, or ""
    events: list[str] = []
    grouped = [ln for ln in group_lines(
        words, max_chars=max_chars, max_words=max_words, max_gap=max_gap) if ln]
    for idx, line in enumerate(grouped):
        # Cap a line's on-screen time at the next line's first word so a finished
        # caption never lingers into the next one (whisper over-stretches the last
        # word's end across a pause — see _pop_events / MAX_WORD_DUR).
        next_start = grouped[idx + 1][0].start if idx + 1 < len(grouped) else None
        if preset is KaraokePreset.POP:
            for start_s, end_s, text in _pop_events(line, style, next_start):
                events.append(
                    f"Dialogue: 0,{ass_timestamp(start_s)},{ass_timestamp(end_s)},"
                    f"{style.name},,0,0,0,,{prefix}{text}"
                )
        else:
            end_s = line[-1].end if next_start is None else min(line[-1].end, next_start)
            start = ass_timestamp(line[0].start)
            end = ass_timestamp(end_s)
            text = _sweep_line_text(line)
            events.append(
                f"Dialogue: 0,{start},{end},{style.name},,0,0,0,,{prefix}{text}"
            )

    return "\n".join(head + events) + "\n"
