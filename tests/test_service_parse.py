"""Unit tests for the shared STT service client (no network/GPU needed)."""
from __future__ import annotations

import pytest

from nulcaption.ass import Word
from nulcaption.transcribe import service


def test_service_url_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WHISPER_HTTP_URL", raising=False)
    assert service.service_url() == service.DEFAULT_SERVICE_URL
    assert service.service_url("http://x:1/inference") == "http://x:1/inference"
    monkeypatch.setenv("WHISPER_HTTP_URL", "http://env:9/inference")
    assert service.service_url() == "http://env:9/inference"
    # explicit override beats the env var
    assert service.service_url("http://x:1/inference") == "http://x:1/inference"


def test_parse_flattens_segment_words() -> None:
    data = {
        "segments": [
            {"text": "", "start": 0.0, "end": 0.1},  # no words -> skipped
            {"text": " my", "words": [{"word": " my", "start": 0.68, "end": 0.73}]},
            {"text": " fellow",
             "words": [{"word": " fellow", "start": 0.73, "end": 1.22}]},
        ]
    }
    assert service._parse_verbose_json(data, max_word_dur=2.0) == [
        Word("my", 0.68, 0.73),
        Word("fellow", 0.73, 1.22),
    ]


def test_parse_merges_punctuation_keeping_real_end() -> None:
    # "," arrives as its own token whose end stretches across the pause; it must
    # fold into "Americans" and keep Americans' real end (1.98), not 2.89.
    data = {
        "segments": [
            {"words": [
                {"word": " Americans", "start": 1.22, "end": 1.98},
                {"word": ",", "start": 1.98, "end": 2.89},
            ]},
        ]
    }
    words = service._parse_verbose_json(data, max_word_dur=2.0)
    assert words == [Word("Americans,", 1.22, 1.98)]


def test_parse_clamps_long_word() -> None:
    data = {"segments": [{"words": [{"word": " uh", "start": 1.0, "end": 9.0}]}]}
    words = service._parse_verbose_json(data, max_word_dur=2.0)
    assert words == [Word("uh", 1.0, 3.0)]


def test_parse_empty() -> None:
    assert service._parse_verbose_json({}, max_word_dur=2.0) == []
    assert service._parse_verbose_json({"segments": []}, max_word_dur=2.0) == []
