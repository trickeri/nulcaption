"""Tests for the ASS karaoke generator, line grouping, and style rendering."""
from __future__ import annotations

from nulcaption import config as cfgmod
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


def test_group_lines_breaks_after_sentence_end() -> None:
    words = [
        Word("That's", 0.0, 0.4), Word("insane,", 0.4, 0.9), Word("dude.", 0.9, 1.4),
        Word("Oh,", 1.5, 1.8), Word("I", 1.8, 2.0),
    ]
    lines = group_lines(words)
    # break after "dude." (sentence end), not lumped with the next sentence
    assert [[w.text for w in ln] for ln in lines] == [
        ["That's", "insane,", "dude."],
        ["Oh,", "I"],
    ]


def test_group_lines_breaks_on_silence() -> None:
    # a long pause (4s) splits the caption even with no punctuation
    words = [Word("hello", 0.0, 0.4), Word("world", 4.4, 4.8)]
    assert len(group_lines(words, max_gap=0.7)) == 2
    # a short pause does not
    words2 = [Word("hello", 0.0, 0.4), Word("world", 0.7, 1.1)]
    assert len(group_lines(words2, max_gap=0.7)) == 1


def test_pop_leaves_silence_uncaptioned() -> None:
    # "That's insane, dude." then ~4.6s silence then "Oh, I" (the reported bug)
    words = [
        Word("That's", 0.0, 0.4), Word("insane,", 0.4, 0.9), Word("dude.", 0.9, 1.4),
        Word("Oh,", 6.0, 6.3), Word("I", 6.3, 6.5),
    ]
    ass = generate_ass(words, preset="pop")

    def _secs(ts: str) -> float:
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    spans = [
        (_secs(p[1]), _secs(p[2]))
        for ln in ass.splitlines()
        if ln.startswith("Dialogue:")
        for p in [ln.split(",")]
    ]
    # nothing on screen at t=3.0s, deep inside the 1.4-6.0s silence
    assert not any(start <= 3.0 <= end for start, end in spans)
    # "dude." and "Oh," never share a caption event
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert not any("dude." in d and "Oh," in d for d in dialogues)


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


def test_pop_line_does_not_linger_into_next() -> None:
    # max_words break mid-sentence; whisper over-stretched the last word "c" of
    # line 1 (end 3.0) well past line 2's first word "d" (start 1.5). The last
    # pop event of line 1 must be capped at 1.5 so the two lines never overlap.
    words = [
        Word("a", 0.0, 0.5), Word("b", 0.5, 1.0), Word("c", 1.0, 3.0),
        Word("d", 1.5, 2.0), Word("e", 2.0, 2.5),
    ]
    ass = generate_ass(words, preset="pop", max_words=3, max_chars=999)

    def _secs(ts: str) -> float:
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    # line-1 events show "a b c"; line-2 events show "d e". No line-1 event may
    # end after line 2's first word (t=1.5), or the old line lingers on screen.
    line1 = [d for d in dialogues if "}a" in d and "}d" not in d]
    assert line1  # sanity: we actually found line-1 events
    assert all(_secs(d.split(",")[2]) <= 1.5 + 1e-9 for d in line1)


def test_sweep_line_capped_at_next_line_start() -> None:
    words = [
        Word("a", 0.0, 0.5), Word("b", 0.5, 1.0), Word("c", 1.0, 3.0),
        Word("d", 1.5, 2.0),
    ]
    ass = generate_ass(words, preset="sweep", max_words=3, max_chars=999)
    first = next(ln for ln in ass.splitlines() if ln.startswith("Dialogue:"))
    # line 1 ends at 1.5 (line 2's start), not at c's stretched end of 3.0
    assert first.split(",")[2] == "0:00:01.50"


def test_middle_alignment_positions_with_margin() -> None:
    # libass ignores MarginV for middle alignment, so we emit an explicit \pos
    # whose y drops as the Y margin grows (margin raises the caption).
    import re

    def _pos_y(margin: int) -> int:
        st = cfgmod.CaptionConfig(alignment=5, margin_v=margin).to_style()
        ass = generate_ass([Word("hi", 0, 1)], style=st, play_res=(1920, 1080))
        d = next(ln for ln in ass.splitlines() if ln.startswith("Dialogue:"))
        m = re.search(r"\\pos\((\d+),(\d+)\)", d)
        assert m, d
        return int(m.group(2))

    assert _pos_y(0) == 540          # dead centre of a 1080 frame
    assert _pos_y(150) == 390        # 150px above centre
    assert _pos_y(150) < _pos_y(0)   # bigger margin -> higher up


def test_bottom_alignment_uses_marginv_not_pos() -> None:
    # top/bottom alignments rely on the style MarginV (which libass honours) and
    # must NOT carry a \pos override.
    for align in (2, 8):
        st = cfgmod.CaptionConfig(alignment=align, margin_v=120).to_style()
        ass = generate_ass([Word("hi", 0, 1)], style=st)
        assert "\\pos(" not in ass
        assert ",120,1" in ass  # MarginV lands in the style line


def test_kdenlive_extradata_block_opt_in() -> None:
    ass = generate_ass([Word("x", 0, 1)], style=NULDRUMS, kdenlive_extradata=True)
    assert "[Kdenlive Extradata]" in ass
    assert "DefaultStyles: Nuldrums" in ass
    # default (burn-in) output stays clean
    assert "[Kdenlive Extradata]" not in generate_ass([Word("x", 0, 1)])
