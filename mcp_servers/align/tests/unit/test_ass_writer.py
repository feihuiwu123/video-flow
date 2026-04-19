"""Unit tests for ASS writer (no faster-whisper dependency)."""

from pathlib import Path
from tempfile import TemporaryDirectory

from videoflow_align.ass_writer import (
    AssStyle,
    Segment,
    WordTiming,
    build_ass,
    write_ass,
)


def test_word_timing_validation():
    """WordTiming rejects end < start."""
    WordTiming("hello", start=0.0, end=1.5)  # OK
    WordTiming("hello", start=1.0, end=1.0)  # OK, zero duration

    import pytest
    with pytest.raises(ValueError, match="end.*<.*start"):
        WordTiming("hello", start=2.0, end=1.0)


def test_build_ass_empty():
    """Empty segment list yields just header."""
    ass = build_ass([])
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    # No Dialogue lines
    assert "Dialogue:" not in ass


def test_build_ass_single_segment_no_words():
    """Segment without words yields plain text line."""
    seg = Segment(start=10.5, end=15.2, text="Hello world")
    ass = build_ass([seg])

    assert "Dialogue:" in ass
    assert "Hello world" in ass
    assert "\\k" not in ass  # No karaoke tags when no words


def test_build_ass_word_level():
    """Segment with words yields karaoke tags."""
    words = [
        WordTiming("Hello", start=10.5, end=11.8),
        WordTiming("world", start=11.8, end=15.2),
    ]
    seg = Segment(start=10.5, end=15.2, text="Hello world", words=words)
    ass = build_ass([seg])

    # Should contain {\kNNN} tags
    assert "{\\k" in ass
    # First word duration: (11.8 - 10.5) = 1.3s → 130 centiseconds
    assert "{\\k130}Hello" in ass or "{\\k130}Hello" in ass.replace(" ", "")
    # Second word: (15.2 - 11.8) = 3.4s → 340 cs
    assert "{\\k340}world" in ass or "{\\k340}world" in ass.replace(" ", "")


def test_build_ass_escaping():
    """Braces and newlines are escaped *within the Dialogue text column*.

    The ASS file itself uses ``\\n`` as a line separator, so we only assert
    the per-event text field is sanitised.
    """
    seg = Segment(start=0, end=1, text="Text {with} braces\nand newline")
    ass = build_ass([seg])

    # Find the dialogue row and inspect only its trailing text column.
    dialogue_lines = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogue_lines) == 1
    text_field = dialogue_lines[0].split(",", 9)[-1]

    # Braces must be replaced with parentheses so ASS override tags don't
    # accidentally activate on user input.
    assert "(with)" in text_field
    assert "{with}" not in text_field
    # Inline newlines collapse to a space; the raw string must survive on one line.
    assert "and newline" in text_field
    assert "\n" not in text_field
    assert "\r" not in text_field


def test_timestamp_formatting():
    """_fmt_timestamp handles edge cases."""
    # Note: _fmt_timestamp is private, but we can test via public API
    from videoflow_align.ass_writer import _fmt_timestamp

    # Basic case
    assert _fmt_timestamp(0.0) == "0:00:00.00"
    assert _fmt_timestamp(1.5) == "0:00:01.50"
    assert _fmt_timestamp(61.5) == "0:01:01.50"
    assert _fmt_timestamp(3661.5) == "1:01:01.50"

    # Rounding to centiseconds
    assert _fmt_timestamp(1.999) == "0:00:02.00"  # rounds up
    assert _fmt_timestamp(1.994) == "0:00:01.99"

    # Negative -> clamped to zero
    assert _fmt_timestamp(-1.0) == "0:00:00.00"


def test_write_ass(tmp_path: Path):
    """write_ass creates file with correct content."""
    words = [WordTiming("Test", start=0, end=1)]
    seg = Segment(start=0, end=1, text="Test", words=words)
    output = tmp_path / "test.ass"

    result = write_ass([seg], output)
    assert result == output
    assert output.exists()

    content = output.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "Dialogue:" in content
    assert "Test" in content


def test_ass_style_custom():
    """Custom AssStyle affects output."""
    style = AssStyle(
        font_name="Arial",
        font_size=72,
        primary_color="&HFF0000",
        secondary_color="&H00FF00",
        outline_color="&H0000FF",
        alignment=8,  # top-left
        margin_v=100,
    )
    ass = build_ass([], style=style)

    assert "Arial" in ass
    assert "72" in ass
    assert "&HFF0000" in ass
    assert "&H00FF00" in ass
    assert "&H0000FF" in ass
    assert "Alignment: 8" not in ass  # Actually in Style line, not separate
    # Check style line contains the alignment
    assert ",8," in ass or ",8\n" in ass