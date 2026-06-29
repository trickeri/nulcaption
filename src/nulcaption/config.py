"""Persisted caption settings shared by the CLI and the settings GUI.

The settings window writes this file; ``nulcaption caption`` reads it as defaults
(explicit CLI flags still win). One flat JSON document at
``$XDG_CONFIG_HOME/nulcaption/config.json`` (``~/.config/nulcaption`` by default;
override the whole path with ``$NULCAPTION_CONFIG``). JSON keeps read+write
dependency-free and round-trippable — the GUI is the intended editor.

Unknown keys in the file are ignored and missing keys fall back to the dataclass
defaults, so a config written by an older/newer version still loads.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .styles.presets import Style


def config_path() -> Path:
    env = os.environ.get("NULCAPTION_CONFIG")
    if env:
        return Path(env)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "nulcaption" / "config.json"


@dataclass
class CaptionConfig:
    """Everything the settings window controls. RGB values are ``RRGGBB`` hex."""

    # --- caption behaviour ---
    preset: str = "pop"            # karaoke look: pop | sweep
    language: str = "auto"
    vad: bool = True
    vad_threshold: float | None = None  # None = whisper default (0.5)
    max_words: int = 7
    max_chars: int = 42

    # --- speech-to-text backend ---
    # Prefer the shared system-wide STT daemon (whispermodel / whisper-server,
    # later Parakeet) when it's running, instead of cold-loading nulcaption's own
    # whisper.cpp model per job. Falls back to the local backend if it's down.
    use_stt_service: bool = True
    stt_service_url: str = ""       # "" = $WHISPER_HTTP_URL or the daemon default

    # --- position ---
    alignment: int = 2             # ASS numpad anchor: 2=bottom-center, 5=middle, 8=top
    margin_v: int = 60             # vertical margin (px) from the anchored edge

    # --- style appearance ---
    style_name: str = "Nuldrums"   # written into the ASS [V4+ Styles] line
    fontname: str = "Pirata One"
    fontsize: int = 72
    highlight_rgb: str = "00FFFF"
    base_rgb: str = "F2F2F2"
    bold: bool = True
    italic: bool = False
    outline_enabled: bool = True
    outline_rgb: str = "000000"
    outline_thickness: float = 4.0
    shadow_enabled: bool = False
    shadow_rgb: str = "000000"
    shadow_x: float = 2.0
    shadow_y: float = 2.0

    # -- conversions --
    def to_style(self) -> Style:
        """Resolve the appearance fields (with toggles applied) into a Style."""
        return Style(
            name=self.style_name,
            fontname=self.fontname,
            fontsize=self.fontsize,
            alignment=self.alignment,
            margin_v=self.margin_v,
            highlight_rgb=self.highlight_rgb,
            base_rgb=self.base_rgb,
            outline_rgb=self.outline_rgb,
            back_rgb=self.shadow_rgb,
            bold=-1 if self.bold else 0,
            italic=-1 if self.italic else 0,
            outline=self.outline_thickness if self.outline_enabled else 0.0,
            shadow=0.0 if not self.shadow_enabled else max(self.shadow_x, self.shadow_y),
            shadow_x=self.shadow_x if self.shadow_enabled else None,
            shadow_y=self.shadow_y if self.shadow_enabled else None,
        )


def _known_keys() -> set[str]:
    return {f.name for f in fields(CaptionConfig)}


def load(path: Path | None = None) -> CaptionConfig:
    """Load config, falling back to defaults for any missing/invalid file."""
    p = path or config_path()
    if not p.is_file():
        return CaptionConfig()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return CaptionConfig()
    if not isinstance(data, dict):
        return CaptionConfig()
    known = _known_keys()
    return CaptionConfig(**{k: v for k, v in data.items() if k in known})


def save(cfg: CaptionConfig, path: Path | None = None) -> Path:
    """Write config atomically; returns the path written."""
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".part")
    tmp.write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p
