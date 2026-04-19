"""Unit tests for videoflow.renderer."""

import pytest
from PIL import Image

from videoflow.models import Renderer, Shot, TitleCardVisual
from videoflow.renderer import (
    _find_font_file,
    _parse_hex_color,
    _wrap_text,
    render_title_card,
)


def _shot(narration: str = "这是一段旁白内容,用来演示字幕。", heading: str = "反常识") -> Shot:
    return Shot(
        shot_id="S01",
        start=0.0,
        end=5.0,
        narration=narration,
        visual=TitleCardVisual(text=heading),
        renderer=Renderer.STATIC,
    )


class TestParseHexColor:
    def test_hash_prefix(self):
        assert _parse_hex_color("#FF0000") == (255, 0, 0)

    def test_zero_x_prefix(self):
        assert _parse_hex_color("0x00FF00") == (0, 255, 0)

    def test_no_prefix(self):
        assert _parse_hex_color("0000FF") == (0, 0, 255)

    def test_mixed_case(self):
        assert _parse_hex_color("#aAbBcC") == (0xAA, 0xBB, 0xCC)

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError):
            _parse_hex_color("#FFF")


class TestWrapText:
    def test_empty_returns_single_empty(self):
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (10, 10))
        draw = ImageDraw.Draw(img)
        assert _wrap_text("", ImageFont.load_default(), 100, draw) == [""]


class TestRenderTitleCard:
    def test_produces_png_of_expected_size(self, tmp_path):
        out = tmp_path / "s01.png"
        render_title_card(_shot(), out, width=1080, height=1920)
        assert out.exists()
        with Image.open(out) as im:
            assert im.size == (1080, 1920)
            assert im.format == "PNG"

    def test_custom_dimensions(self, tmp_path):
        out = tmp_path / "s.png"
        render_title_card(_shot(), out, width=720, height=1280)
        with Image.open(out) as im:
            assert im.size == (720, 1280)

    def test_light_background(self, tmp_path):
        shot = _shot()
        shot.visual = TitleCardVisual(text="Bright", background="light")
        out = tmp_path / "light.png"
        render_title_card(shot, out)
        with Image.open(out) as im:
            px = im.getpixel((10, 10))
            # Light mode uses #F5F5F5 (~245).
            assert all(c >= 200 for c in px[:3])

    def test_dark_background_default(self, tmp_path):
        out = tmp_path / "dark.png"
        render_title_card(_shot(), out, background_color="#0A1929")
        with Image.open(out) as im:
            px = im.getpixel((10, 10))
            assert px[:3] == (0x0A, 0x19, 0x29)

    def test_rejects_non_title_card_visual(self, tmp_path):
        from unittest.mock import Mock

        shot = _shot()
        # Replace with a non-TitleCardVisual sentinel to prove the guard fires.
        shot.visual = Mock(spec=["type"])  # type: ignore[assignment]
        with pytest.raises(TypeError):
            render_title_card(shot, tmp_path / "bad.png")

    def test_output_parent_created(self, tmp_path):
        out = tmp_path / "deep" / "nested" / "s.png"
        render_title_card(_shot(), out)
        assert out.exists()


@pytest.mark.skipif(_find_font_file() is None, reason="no CJK font on host")
class TestFontAvailable:
    def test_font_file_exists(self):
        path = _find_font_file()
        assert path is not None
        assert path.exists()
