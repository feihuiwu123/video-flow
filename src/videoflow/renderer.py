"""Visual renderer — turn a TitleCardVisual into a PNG frame.

Rationale
---------
Many distro-supplied FFmpeg builds (e.g. Homebrew on macOS) ship without
libass / libfreetype / libfontconfig, which means the ``subtitles``,
``ass`` and ``drawtext`` filters are all unavailable. To give every shot
actual on-screen content — heading + narration — we rasterise a PNG in
Python with Pillow and feed that PNG to FFmpeg as the background frame.

Later renderers (Mermaid / Remotion / Playwright — see PRD §6) will
produce their own visuals; this module handles the demo's TitleCardVisual
only.
"""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont

from videoflow.models import Shot, TitleCardVisual

logger = logging.getLogger(__name__)


# Candidate font files per platform, tried in priority order. First match wins.
_FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "Darwin": (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Songti.ttc",
    ),
    "Linux": (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/source-han-sans/SourceHanSans-Regular.otf",
    ),
    "Windows": (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ),
}


def _find_font_file() -> Optional[Path]:
    """Locate a CJK-capable TTF/TTC on the host. Returns ``None`` if none found."""
    system = platform.system()
    for candidate in _FONT_CANDIDATES.get(system, ()):
        p = Path(candidate)
        if p.exists():
            return p
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a Pillow font at ``size``px. Falls back to the default bitmap
    font if no CJK font is available — the result won't render Chinese
    glyphs but it keeps the pipeline running."""
    font_path = _find_font_file()
    if font_path is None:
        logger.warning("No CJK font found on host; Chinese text may show as tofu.")
        return ImageFont.load_default()
    return ImageFont.truetype(str(font_path), size)


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Greedy line-wrap that handles CJK (character-level) and Latin (word-level).

    Chinese has no explicit word boundaries, so we break after any CJK
    character that would push the line past ``max_width``. Latin words
    break on spaces.
    """
    if not text:
        return [""]

    def measure(s: str) -> int:
        # textbbox works for both truetype and default fonts.
        left, _top, right, _bottom = draw.textbbox((0, 0), s, font=font)
        return right - left

    lines: list[str] = []
    buf = ""
    for ch in text:
        candidate = buf + ch
        if measure(candidate) <= max_width:
            buf = candidate
            continue
        # Latin word break: if we just added a non-space and buf has a space,
        # rewind to the last space so we don't split mid-word.
        if ch != " " and " " in buf:
            last_space = buf.rfind(" ")
            lines.append(buf[:last_space])
            buf = buf[last_space + 1 :] + ch
        else:
            lines.append(buf)
            buf = ch
    if buf:
        lines.append(buf)
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    x: int,
    y: int,
    max_width: int,
    fill: tuple[int, int, int],
    line_spacing: float = 1.4,
    highlight_keywords: Iterable[str] = (),
    highlight_fill: tuple[int, int, int] = (255, 209, 102),
) -> int:
    """Draw text wrapped to ``max_width``, return the final y-cursor.

    Keywords in ``highlight_keywords`` are rendered in ``highlight_fill``
    (character-by-character check so CJK substrings work).
    """
    lines = _wrap_text(text, font, max_width, draw)
    if hasattr(font, "size"):
        line_height = int(font.size * line_spacing)
    else:
        line_height = int(16 * line_spacing)
    keywords = tuple(k for k in highlight_keywords if k)

    for line in lines:
        if not keywords:
            draw.text((x, y), line, font=font, fill=fill)
        else:
            cursor_x = x
            i = 0
            while i < len(line):
                matched = False
                for kw in keywords:
                    if line.startswith(kw, i):
                        draw.text((cursor_x, y), kw, font=font, fill=highlight_fill)
                        l, _t, r, _b = draw.textbbox((0, 0), kw, font=font)
                        cursor_x += r - l
                        i += len(kw)
                        matched = True
                        break
                if not matched:
                    ch = line[i]
                    draw.text((cursor_x, y), ch, font=font, fill=fill)
                    l, _t, r, _b = draw.textbbox((0, 0), ch, font=font)
                    cursor_x += r - l
                    i += 1
        y += line_height
    return y


def _parse_hex_color(value: str) -> tuple[int, int, int]:
    """Accept ``#RRGGBB`` or ``0xRRGGBB`` and return an (r, g, b) tuple."""
    cleaned = value.lstrip("#").lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if len(cleaned) != 6:
        raise ValueError(f"Expected 6-digit hex colour, got {value!r}")
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)


def render_title_card(
    shot: Shot,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    background_color: str = "#0A1929",
    title_size: int = 88,
    body_size: int = 56,
    shot_tag_size: int = 40,
    margin: int = 96,
) -> Path:
    """Render one shot's TitleCardVisual to a PNG file.

    Layout (top → bottom):
        1. Small "Shot ID" tag
        2. Heading text (large, bold-ish via title_size)
        3. Narration body (smaller, wrapped)
    """
    if not isinstance(shot.visual, TitleCardVisual):
        raise TypeError(
            f"render_title_card only handles TitleCardVisual, got {type(shot.visual).__name__}"
        )

    visual = shot.visual
    bg_rgb = _parse_hex_color(background_color)
    # Light-mode cards invert to a bright background; the narration colour
    # flips accordingly so there's always adequate contrast.
    if visual.background == "light":
        bg_rgb = (245, 245, 245)
        text_color = (20, 30, 50)
        sub_color = (80, 90, 110)
        tag_color = (120, 120, 130)
    else:
        text_color = (255, 255, 255)
        sub_color = (200, 210, 225)
        tag_color = (120, 180, 220)

    image = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(title_size)
    body_font = _load_font(body_size)
    tag_font = _load_font(shot_tag_size)

    content_width = width - 2 * margin

    y = margin
    draw.text((margin, y), shot.shot_id, font=tag_font, fill=tag_color)
    y += int(shot_tag_size * 1.6) + 24

    # Title block.
    y = _draw_wrapped(
        draw,
        visual.text,
        title_font,
        margin,
        y,
        content_width,
        fill=text_color,
        line_spacing=1.35,
        highlight_keywords=visual.highlight_keywords,
    )

    # Separator.
    y += 40
    draw.rectangle((margin, y, margin + 80, y + 6), fill=tag_color)
    y += 60

    # Narration body.
    _draw_wrapped(
        draw,
        shot.narration,
        body_font,
        margin,
        y,
        content_width,
        fill=sub_color,
        line_spacing=1.5,
        highlight_keywords=visual.highlight_keywords,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path
