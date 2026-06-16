"""Style presets rendered into ASS ``[V4+ Styles]`` lines.

ASS colours are ``&HAABBGGRR`` (alpha, blue, green, red; alpha 00 = opaque).
In karaoke, un-swept text shows ``SecondaryColour`` and the sweep fills to
``PrimaryColour`` — so for highlighting, Primary = highlight, Secondary = base.
"""
from __future__ import annotations

from dataclasses import dataclass


def ass_colour(rgb: str, alpha: int = 0) -> str:
    """``"6E2C8B"`` (RRGGBB) -> ``"&H006E2C8B"``-style ``&HAABBGGRR``."""
    rgb = rgb.lstrip("#")
    if len(rgb) != 6:
        raise ValueError(f"expected RRGGBB hex, got {rgb!r}")
    rr, gg, bb = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"&H{alpha:02X}{bb}{gg}{rr}".upper()


def ass_override_colour(rgb: str) -> str:
    """``"6E2C8B"`` (RRGGBB) -> ``"&H8B2C6E&"`` for inline ``\\1c``/``\\c`` blocks.

    The override form is ``&HBBGGRR&`` (no alpha byte, trailing ``&``) — distinct
    from the ``&HAABBGGRR`` form used in ``[V4+ Styles]`` lines.
    """
    rgb = rgb.lstrip("#")
    if len(rgb) != 6:
        raise ValueError(f"expected RRGGBB hex, got {rgb!r}")
    rr, gg, bb = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"&H{bb}{gg}{rr}&".upper()


@dataclass(frozen=True, slots=True)
class Style:
    name: str
    fontname: str
    fontsize: int
    # highlight (swept/active) and base (un-swept) colours, RRGGBB
    highlight_rgb: str
    base_rgb: str
    outline_rgb: str = "000000"   # ASS OutlineColour
    back_rgb: str = "000000"      # ASS BackColour = the drop-shadow colour
    bold: int = -1                # ASS: -1 true, 0 false
    italic: int = 0               # ASS: -1 true, 0 false
    outline: float = 3.0          # outline thickness px (0 disables the outline)
    shadow: float = 1.0           # scalar shadow depth (0 disables; see shadow_x/y)
    # Optional explicit drop-shadow offsets. ASS's Shadow field is a single
    # scalar (down-right diagonal); to offset X and Y independently we emit
    # libass \xshad/\yshad override tags per event (see event_overrides()).
    # When both are None the scalar `shadow` is used as-is.
    shadow_x: float | None = None
    shadow_y: float | None = None
    alignment: int = 2      # numpad: 2 = bottom-center
    margin_v: int = 60

    def to_ass_style_line(self) -> str:
        return (
            f"Style: {self.name},{self.fontname},{self.fontsize},"
            f"{ass_colour(self.highlight_rgb)},{ass_colour(self.base_rgb)},"
            f"{ass_colour(self.outline_rgb)},{ass_colour(self.back_rgb, 0)},"
            f"{self.bold},{self.italic},0,0,100,100,0,0,1,{self.outline},{self.shadow},"
            f"{self.alignment},40,40,{self.margin_v},1"
        )

    def event_overrides(self) -> str:
        """libass override tags prefixed on every Dialogue event, or ``""``.

        Used for things the scalar ``[V4+ Styles]`` line can't express — namely
        independent drop-shadow X/Y offsets via ``\\xshad``/``\\yshad``.
        """
        if self.shadow_x is None and self.shadow_y is None:
            return ""
        x = self.shadow if self.shadow_x is None else self.shadow_x
        y = self.shadow if self.shadow_y is None else self.shadow_y
        return f"{{\\xshad{x:g}\\yshad{y:g}}}"

    @staticmethod
    def format_line() -> str:
        return (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        )


# Nuldrums brand: Pirata One, cyan highlight on near-white base, 4px black outline.
NULDRUMS = Style(
    name="Nuldrums",
    fontname="Pirata One",
    fontsize=72,
    highlight_rgb="00FFFF",   # cyan
    base_rgb="F2F2F2",
    outline_rgb="000000",     # black
    outline=4.0,
)

# Trikeri: Oswald (Google font), same cyan highlight + 4px black outline.
TRIKERI = Style(
    name="Trikeri",
    fontname="Oswald",
    fontsize=72,
    highlight_rgb="00FFFF",   # cyan
    base_rgb="F2F2F2",
    outline_rgb="000000",     # black
    outline=4.0,
)

PLAIN = Style(
    name="Plain",
    fontname="Arial",
    fontsize=64,
    highlight_rgb="FFD400",   # yellow sweep
    base_rgb="FFFFFF",
    outline_rgb="000000",
)

PRESETS: dict[str, Style] = {"nuldrums": NULDRUMS, "trikeri": TRIKERI, "plain": PLAIN}
