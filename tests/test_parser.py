"""Unit tests for videoflow.parser."""

import pytest

from videoflow.parser import _estimate_duration, _split_paragraphs, parse_markdown


class TestSplitParagraphs:
    def test_headings_produce_sections(self):
        md = "# Title\nIntro text.\n\n## Section A\nBody A.\n\n## Section B\nBody B."
        sections = _split_paragraphs(md)
        assert len(sections) == 3
        assert sections[0][0] == "Title"
        assert sections[1][0] == "Section A"
        assert "Body B" in sections[2][1]

    def test_body_joined_on_spaces(self):
        md = "## Head\nline one.\nline two."
        (heading, body), = _split_paragraphs(md)
        assert heading == "Head"
        assert body == "line one. line two."

    def test_heading_without_body_uses_heading_as_body(self):
        md = "## Only heading"
        sections = _split_paragraphs(md)
        assert sections == [("Only heading", "Only heading")]

    def test_body_without_heading_uses_first_chars(self):
        md = "Just a body paragraph without any heading at all."
        sections = _split_paragraphs(md)
        assert len(sections) == 1
        assert sections[0][0]  # non-empty fallback heading
        assert sections[0][1] == "Just a body paragraph without any heading at all."

    def test_empty_input_returns_empty(self):
        assert _split_paragraphs("\n\n\n   ") == []


class TestEstimateDuration:
    def test_short_text_clamped_to_min(self):
        assert _estimate_duration("短") == pytest.approx(3.0)

    def test_long_text_clamped_to_max(self):
        assert _estimate_duration("长" * 1000) == pytest.approx(20.0)


class TestParseMarkdown:
    def test_produces_valid_shotlist(self):
        md = "# 标题\n第一段内容。\n\n## 第二节\n第二段内容。"
        sl = parse_markdown(md)
        assert len(sl.shots) == 2
        assert sl.shots[0].shot_id == "S01"
        assert sl.shots[1].shot_id == "S02"
        # Timings monotonic.
        assert sl.shots[0].end == sl.shots[1].start

    def test_shot_ids_zero_padded(self):
        md = "\n\n".join(f"## H{i}\nbody{i}." for i in range(1, 12))
        sl = parse_markdown(md)
        assert sl.shots[0].shot_id == "S01"
        assert sl.shots[9].shot_id == "S10"
        assert sl.shots[10].shot_id == "S11"

    def test_empty_markdown_raises(self):
        with pytest.raises(ValueError):
            parse_markdown("")
