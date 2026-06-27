from __future__ import annotations

from dataclasses import replace

from nulcaption.ass import Word, generate_ass
from nulcaption.ass.restyle import restyle_ass_text
from nulcaption.styles import NULDRUMS
from nulcaption.styles.presets import ass_colour, ass_override_colour


def _pop_ass() -> str:
    words = [Word("hello", 0.0, 0.4), Word("world", 0.4, 0.9)]
    return generate_ass(words, style=NULDRUMS, preset="pop")


def test_restyle_repositions_and_keeps_style_name() -> None:
    ass = _pop_ass()
    target = replace(NULDRUMS, alignment=8, margin_v=240)
    out = restyle_ass_text(ass, target)
    style_lines = [ln for ln in out.splitlines() if ln.startswith("Style:")]
    assert len(style_lines) == 1
    fields = style_lines[0].split(",")
    # name preserved
    assert fields[0] == "Style: Nuldrums"
    # Alignment (field idx 18) and MarginV (idx 21) updated
    assert fields[18] == "8"
    assert fields[21] == "240"


def test_restyle_recolours_pop_events() -> None:
    ass = _pop_ass()
    # NULDRUMS: highlight cyan 00FFFF, base F2F2F2. Restyle to red highlight / black base.
    target = replace(NULDRUMS, highlight_rgb="FF0000", base_rgb="000000")
    out = restyle_ass_text(ass, target)
    event_lines = [ln for ln in out.splitlines() if ln.startswith("Dialogue:")]
    body = "\n".join(event_lines)
    # old per-word colours gone, new ones present
    assert ass_override_colour("00FFFF") not in body
    assert ass_override_colour("F2F2F2") not in body
    assert ass_override_colour("FF0000") in body
    assert ass_override_colour("000000") in body
    # style line PrimaryColour (highlight) updated too
    style_line = next(ln for ln in out.splitlines() if ln.startswith("Style:"))
    assert ass_colour("FF0000") in style_line


def test_restyle_preserves_trailing_newline() -> None:
    ass = _pop_ass()
    assert ass.endswith("\n")
    assert restyle_ass_text(ass, NULDRUMS).endswith("\n")
