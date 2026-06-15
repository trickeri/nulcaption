"""Tests for Path A: preparing a Kdenlive-native subtitle-track .ass."""
from __future__ import annotations

from pathlib import Path

from nulcaption.ass import Word, generate_ass
from nulcaption.integration import apply_native_track
from nulcaption.integration.paths import _ensure_kdenlive_native, _first_style_name
from nulcaption.styles import NULDRUMS


def _sample_ass() -> str:
    return generate_ass([Word("hello", 0.0, 0.8), Word("world", 0.8, 1.6)], style=NULDRUMS)


def test_first_style_name() -> None:
    assert _first_style_name(_sample_ass()) == "Nuldrums"
    assert _first_style_name("[Events]\nDialogue: ...") is None


def test_ensure_native_inserts_block_before_styles() -> None:
    native = _ensure_kdenlive_native(_sample_ass())
    assert "[Kdenlive Extradata]" in native
    assert "DefaultStyles: Nuldrums" in native
    # block precedes the styles section
    assert native.index("[Kdenlive Extradata]") < native.index("[V4+ Styles]")


def test_ensure_native_is_idempotent() -> None:
    once = _ensure_kdenlive_native(_sample_ass())
    twice = _ensure_kdenlive_native(once)
    assert once == twice
    assert twice.count("[Kdenlive Extradata]") == 1


def test_apply_native_track_preserves_karaoke_tags(tmp_path: Path) -> None:
    src = tmp_path / "clip.ass"
    src.write_text(_sample_ass(), encoding="utf-8")
    out = apply_native_track(src)
    assert out == tmp_path / "clip.kdenlive.ass"
    text = out.read_text(encoding="utf-8")
    # the karaoke override tags and the custom style survive untouched
    assert r"{\kf80}hello" in text
    assert "Style: Nuldrums," in text
    assert "[Kdenlive Extradata]" in text


def test_apply_native_track_custom_out(tmp_path: Path) -> None:
    src = tmp_path / "clip.ass"
    src.write_text(_sample_ass(), encoding="utf-8")
    dst = tmp_path / "subs" / "track.ass"
    dst.parent.mkdir()
    out = apply_native_track(src, out=dst)
    assert out == dst and dst.is_file()
