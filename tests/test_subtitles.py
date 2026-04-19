"""Unit tests for videoflow.subtitles."""

from videoflow.models import Renderer, Shot, ShotList, TitleCardVisual
from videoflow.subtitles import AssStyle, _escape_text, _fmt_timestamp, build_ass, write_ass


def _shotlist():
    shots = [
        Shot(
            shot_id="S01",
            start=0.0,
            end=3.5,
            narration="第一段旁白。",
            visual=TitleCardVisual(text="标题"),
            renderer=Renderer.STATIC,
        ),
        Shot(
            shot_id="S02",
            start=3.5,
            end=8.0,
            narration="第二段旁白,包含{curly}字符。",
            visual=TitleCardVisual(text="第二"),
            renderer=Renderer.STATIC,
        ),
    ]
    return ShotList(shots=shots)


class TestFmtTimestamp:
    def test_zero(self):
        assert _fmt_timestamp(0) == "0:00:00.00"

    def test_sub_second(self):
        assert _fmt_timestamp(1.25) == "0:00:01.25"

    def test_minutes_and_hours(self):
        # 1h 2m 3.4s
        assert _fmt_timestamp(3723.4) == "1:02:03.40"

    def test_negative_clamped(self):
        assert _fmt_timestamp(-1) == "0:00:00.00"

    def test_centisecond_rounding_overflow(self):
        # 0.999s should round to 1.00s, not 0.100s
        assert _fmt_timestamp(0.999) == "0:00:01.00"


class TestEscapeText:
    def test_curly_braces_replaced(self):
        assert _escape_text("a{b}c") == "a(b)c"

    def test_newline_replaced_with_space(self):
        assert _escape_text("line1\nline2") == "line1 line2"


class TestBuildAss:
    def test_contains_required_sections(self):
        content = build_ass(_shotlist())
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content

    def test_one_event_per_shot(self):
        content = build_ass(_shotlist())
        events = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        assert len(events) == 2
        # First event runs from 0 to 3.5.
        assert "0:00:00.00,0:00:03.50" in events[0]

    def test_escaping_applied(self):
        content = build_ass(_shotlist())
        assert "(curly)" in content
        assert "{curly}" not in content  # only ASS override braces remain

    def test_style_values_respected(self):
        style = AssStyle(font_name="Custom", font_size=99, margin_v=120)
        content = build_ass(_shotlist(), style)
        assert "Custom,99" in content
        # margin_v is the final MarginV value in the Style line.
        style_line = [ln for ln in content.splitlines() if ln.startswith("Style: Default")][0]
        assert ",120,1" in style_line


class TestWriteAss:
    def test_writes_file(self, tmp_path):
        path = tmp_path / "nested" / "out.ass"
        result = write_ass(_shotlist(), path)
        assert result == path
        assert path.exists()
        assert "[Events]" in path.read_text(encoding="utf-8")
