"""Unit tests for whisper.cpp JSON normalisation (no GPU/model needed)."""
from __future__ import annotations

from nulcaption.ass import Word
from nulcaption.transcribe.backend import _parse_whisper_json


def test_parse_offsets_ms_to_seconds() -> None:
    data = {
        "transcription": [
            {"text": " Hello", "offsets": {"from": 0, "to": 800}},
            {"text": " world", "offsets": {"from": 820, "to": 1600}},
        ]
    }
    words = _parse_whisper_json(data)
    assert words == [
        Word("Hello", 0.0, 0.8),
        Word("world", 0.82, 1.6),
    ]


def test_parse_skips_empty_and_clamps_negative_duration() -> None:
    data = {
        "transcription": [
            {"text": "   ", "offsets": {"from": 0, "to": 100}},      # dropped
            {"text": "ok", "offsets": {"from": 500, "to": 400}},      # end<start -> clamp
        ]
    }
    words = _parse_whisper_json(data)
    assert len(words) == 1
    assert words[0].text == "ok"
    assert words[0].end == words[0].start == 0.5


def test_parse_empty_transcription() -> None:
    assert _parse_whisper_json({"transcription": []}) == []
    assert _parse_whisper_json({}) == []
