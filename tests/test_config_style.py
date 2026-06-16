"""Settings config round-trip + style appearance (italic, outline/shadow toggles)."""
from __future__ import annotations

from pathlib import Path

from nulcaption import config as cfgmod
from nulcaption.ass.karaoke import KaraokePreset, generate_ass
from nulcaption.transcribe.backend import MAX_WORD_DUR, _parse_whisper_json


def test_config_round_trip(tmp_path: Path) -> None:
    cfg = cfgmod.CaptionConfig(
        preset="sweep", italic=True, shadow_enabled=True, shadow_x=3, shadow_y=1,
        outline_enabled=False, vad_threshold=0.65,
    )
    p = tmp_path / "config.json"
    cfgmod.save(cfg, p)
    assert cfgmod.load(p) == cfg


def test_load_missing_and_unknown_keys(tmp_path: Path) -> None:
    # missing file -> defaults
    assert cfgmod.load(tmp_path / "nope.json") == cfgmod.CaptionConfig()
    # unknown keys ignored, known keys applied
    (tmp_path / "c.json").write_text('{"preset":"sweep","bogus":123}')
    assert cfgmod.load(tmp_path / "c.json").preset == "sweep"


def test_to_style_applies_toggles() -> None:
    st = cfgmod.CaptionConfig(
        bold=False, italic=True, outline_enabled=False,
        shadow_enabled=True, shadow_x=4, shadow_y=2,
    ).to_style()
    assert st.bold == 0 and st.italic == -1
    assert st.outline == 0.0                      # outline toggled off
    assert st.event_overrides() == r"{\xshad4\yshad2}"
    line = st.to_ass_style_line()
    # ...,Bold,Italic,... -> 0,-1 right after the two colours+back colour
    assert ",0,-1,0,0," in line


def test_shadow_off_emits_no_override() -> None:
    st = cfgmod.CaptionConfig(shadow_enabled=False).to_style()
    assert st.event_overrides() == ""


def test_shadow_override_prefixes_events() -> None:
    words = [_parse_whisper_json({"transcription": [
        {"text": "hi", "offsets": {"from": 0, "to": 300}},
    ]})[0]]
    st = cfgmod.CaptionConfig(shadow_enabled=True, shadow_x=2, shadow_y=2).to_style()
    out = generate_ass(words, style=st, preset=KaraokePreset.POP)
    assert r"{\xshad2\yshad2}" in out


def test_word_end_clamped_to_max_dur() -> None:
    # whisper smears a word end across a pause; parser clamps it
    w = _parse_whisper_json({"transcription": [
        {"text": "I", "offsets": {"from": 46810, "to": 57880}},
    ]})[0]
    assert w.end - w.start == MAX_WORD_DUR
