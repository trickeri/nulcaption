"""Restyle / reposition an existing karaoke ASS *in place* — no re-transcription.

Rewrites the ``[V4+ Styles]`` ``Style:`` line (position, font, size, weight,
outline, scalar shadow, colours) from a :class:`~nulcaption.styles.presets.Style`,
and swaps the per-word ``\\1c`` highlight/base colour overrides in pop events to
match. Used by the Kdenlive fork's "Restyle Captions" action, which feeds it the
subtitle track's working ``.ass`` and reloads the result.

The existing style NAME is preserved so events keep referencing it. Old per-word
colours are recovered from the old Style line (Primary = highlight, Secondary =
base — the same convention the generator emits), so changing the highlight/base
colours in settings recolours existing pop captions too.
"""
from __future__ import annotations

import re
from dataclasses import replace

from ..styles.presets import Style, ass_override_colour

_STYLE_RE = re.compile(r"^Style:\s*([^,]+),(.*)$")
# A per-word colour override in an event: \1c&HBBGGRR&
_OVERRIDE_1C_RE = re.compile(r"\\1c(&H[0-9A-Fa-f]{6}&)")


def _style_colours(body: str) -> tuple[str | None, str | None]:
    """From a ``Style:`` line's field list (everything after the name) return the
    (PrimaryColour, SecondaryColour) raw ``&HAABBGGRR`` strings, or (None, None)."""
    fields = body.split(",")
    # after the name: Fontname(0) Fontsize(1) Primary(2) Secondary(3) ...
    if len(fields) < 4:
        return None, None
    return fields[2].strip(), fields[3].strip()


def _override_from_style_colour(style_colour: str) -> str | None:
    """``&HAABBGGRR`` (style form) -> ``&HBBGGRR&`` (the ``\\1c`` override form)."""
    m = re.fullmatch(r"&H[0-9A-Fa-f]{2}([0-9A-Fa-f]{6})&?", style_colour.strip())
    if not m:
        return None
    return f"&H{m.group(1).upper()}&"


def _swap_event_colours(text: str, mapping: dict[str, str]) -> str:
    """Replace ``\\1c<old>`` with ``\\1c<new>`` for each old->new in ``mapping``,
    in a single pass (so a new colour can't be re-matched by a later mapping)."""
    def repl(m: re.Match[str]) -> str:
        return "\\1c" + mapping.get(m.group(1).upper(), m.group(1))

    return _OVERRIDE_1C_RE.sub(repl, text)


def restyle_ass_text(text: str, style: Style) -> str:
    """Return ``text`` (a full ASS document) with every ``Style:`` line replaced by
    ``style`` (keeping each line's original name) and pop ``\\1c`` colours remapped."""
    new_hl = ass_override_colour(style.highlight_rgb)
    new_base = ass_override_colour(style.base_rgb)
    mapping: dict[str, str] = {}
    out: list[str] = []
    # split("\n") (not splitlines) so a trailing newline round-trips exactly.
    for line in text.split("\n"):
        m = _STYLE_RE.match(line)
        if not m:
            out.append(line)
            continue
        name = m.group(1).strip()
        old_primary, old_secondary = _style_colours(m.group(2))
        if old_primary and (ovr := _override_from_style_colour(old_primary)):
            mapping[ovr] = new_hl
        if old_secondary and (ovr := _override_from_style_colour(old_secondary)):
            mapping[ovr] = new_base
        out.append(replace(style, name=name).to_ass_style_line())
    result = "\n".join(out)
    if mapping:
        result = _swap_event_colours(result, mapping)
    return result
