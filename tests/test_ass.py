"""Tests for the ASS karaoke generator, line grouping, and style rendering."""
from __future__ import annotations

from nulcaption.ass import Word, ass_timestamp, group_lines, generate_ass
from nulcaption.ass.karaoke import KaraokePreset, _cs
from nulcaption.styles import NULDRUMS
from nulcaption.styles.presets import ass_colour, ass_override_colour


def test_ass_timestamp_centiseconds() -> None:
    assert ass_timestamp(0) == "0:00:00.00"
    assert ass_timestamp(1.23) == "0:00:01.23"
    assert ass_timestamp(61.5) == "0:01:01.50"
    assert ass_timestamp(3661.07) == "1:01:01.07"
    assert ass_timestamp(-5) == "0:00:00.00"


def test_cs_minimum_one() -> None:
    assert _cs(0) == 1
    assert _cs(0.8) == 80


def test_ass_colour_byte_order() -> None:
    # RRGGBB -> &HAABBGGRR
    assert ass_colour("B57EDC") == "&H00DC7EB5"
    assert ass_colour("#000000", alpha=0) == "&H00000000"


def test_group_lines_respects_word_cap() -> None:
    words = [Word(str(i), i, i + 1) for i in range(10)]
    lines = group_lines(words, max_chars=1000, max_words=3)
    assert [len(ln) for ln in lines] == [3, 3, 3, 1]


def test_group_lines_respects_char_cap() -> None:
    words = [Word("aaaa", 0, 1), Word("bbbb", 1, 2), Word("cccc", 2, 3)]
    lines = group_lines(words, max_chars=9, max_words=99)
    # "aaaa bbbb" = 9 chars fits; adding " cccc" exceeds -> new line
    assert [len(ln) for ln in lines] == [2, 1]


def test_generate_ass_sweep_structure() -> None:
    words = [Word("hello", 0.0, 0.8), Word("world", 0.8, 1.6)]
    ass = generate_ass(words, style=NULDRUMS, preset="sweep")
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "Style: Nuldrums," in ass
    assert "[Events]" in ass
    # one line, both words present as \kf runs
    assert "Dialogue: 0,0:00:00.00,0:00:01.60,Nuldrums," in ass
    assert r"{\kf80}hello" in ass
    assert r"{\kf80}world" in ass


def test_generate_ass_inserts_gap_hold() -> None:
    words = [Word("a", 0.0, 0.5), Word("b", 1.0, 1.5)]  # 0.5s gap
    ass = generate_ass(words)
    assert r"{\k50}" in ass  # gap rendered as a \k hold on the space


def test_pop_preset_emits_one_event_per_word() -> None:
    words = [Word("hi", 0.0, 0.4), Word("there", 0.4, 0.9), Word("you", 0.9, 1.4)]
    ass = generate_ass(words, preset=KaraokePreset.POP, max_words=99, max_chars=999)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    # one line of 3 words -> 3 pop events, the whole line shown in each
    assert len(dialogues) == 3
    for d in dialogues:
        assert "hi" in d and "there" in d and "you" in d


def test_pop_highlights_only_the_active_word() -> None:
    words = [Word("a", 0.0, 0.5), Word("b", 0.5, 1.0)]
    ass = generate_ass(words, style=NULDRUMS, preset="pop", max_words=99)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    hl = ass_override_colour(NULDRUMS.highlight_rgb)
    # first event lights "a", second lights "b" (pure highlight-colour switch)
    assert f"{{\\1c{hl}}}a" in dialogues[0]
    assert f"{{\\1c{hl}}}b" in dialogues[1]
    # exactly one highlighted word per event; no scaling tags
    assert dialogues[0].count(hl) == 1
    assert dialogues[1].count(hl) == 1
    assert "\\fscx" not in ass


def test_pop_holds_highlight_until_next_word_over_a_gap() -> None:
    # 0.4s gap between words: first event should hold to the next word's start
    words = [Word("a", 0.0, 0.5), Word("b", 0.9, 1.4)]
    ass = generate_ass(words, preset="pop", max_words=99)
    first = next(ln for ln in ass.splitlines() if ln.startswith("Dialogue:"))
    assert "0:00:00.00,0:00:00.90" in first  # ends where word "b" begins


def test_kdenlive_extradata_block_opt_in() -> None:
    ass = generate_ass([Word("x", 0, 1)], style=NULDRUMS, kdenlive_extradata=True)
    assert "[Kdenlive Extradata]" in ass
    assert "DefaultStyles: Nuldrums" in ass
    # default (burn-in) output stays clean
    assert "[Kdenlive Extradata]" not in generate_ass([Word("x", 0, 1)])
