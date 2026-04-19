"""Visual renderer — turn various VisualSpec types into images/video frames.

Supported renderers:
- TitleCardVisual → PNG (Pillow, STATIC renderer)
- ChartVisual → PNG (Pillow, STATIC renderer)
- DiagramVisual → PNG/SVG (Mermaid CLI if available, else PIL fallback)
- ImageVisual → PNG (Pillow, loads from file/URL)

Rationale
---------
Many distro-supplied FFmpeg builds (e.g. Homebrew on macOS) ship without
libass / libfreetype / libfontconfig. To give every shot actual on-screen
content we rasterise visuals in Python with Pillow and feed that to FFmpeg
as the background frame.

For DiagramVisual, we use Mermaid-CLI if available to render SVG, then
convert to PNG. If Mermaid is not available, we create a fallback text
diagram image.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Union

from PIL import Image, ImageDraw, ImageFont

from videoflow.models import (
    AnyVisual,
    ChartVisual,
    DiagramVisual,
    ImageVisual,
    Shot,
    TitleCardVisual,
)

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

# Color schemes for charts
_COLOR_SCHEMES = {
    "default": ["#4A90D9", "#50C878", "#FFD166", "#EF476F", "#06D6A0", "#118AB2", "#073B4C"],
    "finance": ["#1E3A5F", "#2E7D32", "#C62828", "#F57C00", "#1565C0", "#00838F"],
    "warm": ["#E65100", "#FF8F00", "#FFC107", "#FFD54F", "#FFB300", "#FFA000"],
    "cool": ["#0288D1", "#039BE5", "#03A9F4", "#29B6F6", "#4FC3F7", "#81D4FA"],
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
    font if no CJK font is available."""
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
        left, _top, right, _bottom = draw.textbbox((0, 0), s, font=font)
        return right - left

    lines: list[str] = []
    buf = ""
    for ch in text:
        candidate = buf + ch
        if measure(candidate) <= max_width:
            buf = candidate
            continue
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

    Keywords in ``highlight_keywords`` are rendered in ``highlight_fill``.
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


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    if hex_color.startswith("#"):
        hex_color = hex_color[1:]
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


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

    y += 40
    draw.rectangle((margin, y, margin + 80, y + 6), fill=tag_color)
    y += 60

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


def render_chart(
    shot: Shot,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    background_color: str = "#0A1929",
    margin: int = 96,
) -> Path:
    """Render ChartVisual to a PNG file.

    Renders bar, line, pie, and scatter charts using Pillow.
    """
    if not isinstance(shot.visual, ChartVisual):
        raise TypeError(
            f"render_chart only handles ChartVisual, got {type(shot.visual).__name__}"
        )

    visual = shot.visual
    bg_rgb = _parse_hex_color(background_color)
    text_color = (255, 255, 255)
    sub_color = (200, 210, 225)
    tag_color = (120, 180, 220)

    image = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(image)

    tag_font = _load_font(40)
    title_font = _load_font(64)
    label_font = _load_font(36)

    content_width = width - 2 * margin

    y = margin

    # Shot ID tag
    draw.text((margin, y), shot.shot_id, font=tag_font, fill=tag_color)
    y += int(40 * 1.6) + 24

    # Chart title
    if visual.title:
        y = _draw_wrapped(
            draw,
            visual.title,
            title_font,
            margin,
            y,
            content_width,
            fill=text_color,
            line_spacing=1.3,
        )
        y += 40

    # Parse data
    labels = visual.data.get("labels", [])
    values = visual.data.get("values", [])

    if not values:
        # No data, draw a placeholder
        _draw_wrapped(draw, "No data available", label_font, margin, y, content_width, fill=sub_color)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG", optimize=True)
        return output_path

    # Get colors for chart
    colors = _COLOR_SCHEMES.get(visual.color_scheme, _COLOR_SCHEMES["default"])

    chart_top = y + 60
    chart_bottom = height - margin - 200
    chart_left = margin + 100
    chart_right = width - margin - 50
    chart_height = chart_bottom - chart_top
    chart_width = chart_right - chart_left

    if visual.chart_type == "bar":
        _render_bar_chart(draw, labels, values, colors, chart_left, chart_top, chart_width, chart_height, label_font, sub_color)
    elif visual.chart_type == "line":
        _render_line_chart(draw, labels, values, colors, chart_left, chart_top, chart_width, chart_height, label_font, sub_color)
    elif visual.chart_type == "pie":
        _render_pie_chart(draw, labels, values, colors, width // 2, chart_top + chart_height // 2, min(chart_width, chart_height) // 2 - 50, label_font)
    elif visual.chart_type == "scatter":
        _render_scatter_chart(draw, labels, values, colors, chart_left, chart_top, chart_width, chart_height, label_font, sub_color)

    # Narration text at bottom
    narration_y = height - margin - 150
    _draw_wrapped(
        draw,
        shot.narration,
        label_font,
        margin,
        narration_y,
        content_width,
        fill=sub_color,
        line_spacing=1.5,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def _render_bar_chart(
    draw: ImageDraw.ImageDraw,
    labels: list[str],
    values: list[float],
    colors: list[str],
    left: int,
    top: int,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text_color: tuple[int, int, int],
) -> None:
    """Render a bar chart."""
    if not values:
        return

    max_value = max(abs(v) for v in values) if values else 1
    if max_value == 0:
        max_value = 1

    num_bars = len(values)
    bar_width = min((width - 20) / num_bars - 10, 80)
    gap = (width - num_bars * bar_width) / (num_bars + 1) if num_bars > 0 else 20

    for i, (label, value) in enumerate(zip(labels, values)):
        abs_value = abs(value)
        bar_height = max(1, int((abs_value / max_value) * height))
        x = left + int(gap + i * (bar_width + gap))
        y_top = top + height - bar_height

        color = _hex_to_rgb(colors[i % len(colors)])
        draw.rectangle([x, y_top, x + int(bar_width), top + height], fill=color)

        # Value label on top of bar
        value_text = f"{value:.0f}"
        text_bbox = draw.textbbox((0, 0), value_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text((x + (int(bar_width) - text_width) // 2, y_top - 35), value_text, font=font, fill=text_color)

        # X-axis label
        draw.text((x, top + height + 10), label[:15], font=font, fill=text_color)


def _render_line_chart(
    draw: ImageDraw.ImageDraw,
    labels: list[str],
    values: list[float],
    colors: list[str],
    left: int,
    top: int,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text_color: tuple[int, int, int],
) -> None:
    """Render a line chart."""
    if not values or len(values) < 2:
        return

    max_value = max(values) if values else 1
    min_value = min(values) if values else 0
    value_range = max_value - min_value if max_value != min_value else 1

    num_points = len(values)
    step_x = width / (num_points - 1) if num_points > 1 else width

    points: list[tuple[int, int]] = []
    for i, value in enumerate(values):
        x = left + int(i * step_x)
        normalized = (value - min_value) / value_range
        y = top + int(height - normalized * height)
        points.append((x, y))

    # Draw line
    if points:
        color = _hex_to_rgb(colors[0])
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=color, width=4)

        # Draw points
        for x, y in points:
            draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=color)

        # X-axis labels
        for i, label in enumerate(labels):
            x = left + int(i * step_x)
            draw.text((x - len(label) * 6, top + height + 10), label[:15], font=font, fill=text_color)

        # Y-axis labels
        for v, label in [(min_value, f"{min_value:.0f}"), ((min_value + max_value) / 2, f"{(min_value + max_value) / 2:.0f}"), (max_value, f"{max_value:.0f}")]:
            y = top + int(height - (v - min_value) / value_range * height)
            draw.text((left - 60, y - 15), label, font=font, fill=text_color)


def _render_pie_chart(
    draw: ImageDraw.ImageDraw,
    labels: list[str],
    values: list[float],
    colors: list[str],
    cx: int,
    cy: int,
    radius: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Render a pie chart."""
    if not values:
        return

    total = sum(values)
    if total == 0:
        return

    start_angle = 0
    legend_y = cy + radius + 40

    for i, (label, value) in enumerate(zip(labels, values)):
        if value <= 0:
            continue

        proportion = value / total
        end_angle = start_angle + proportion * 360

        color = _hex_to_rgb(colors[i % len(colors)])

        # Draw pie slice as a polygon
        points = [(cx, cy)]
        num_segments = int(abs(end_angle - start_angle)) + 1
        for seg in range(num_segments + 1):
            angle = (start_angle + seg / num_segments * (end_angle - start_angle)) * 3.14159 / 180
            x = int(cx + radius * abs(__import__('math').cos(angle)))
            y = int(cy + radius * abs(__import__('math').sin(angle)))
            points.append((x, y))
        points.append((cx, cy))

        draw.polygon(points, fill=color, outline=(40, 40, 40))

        # Draw label line and text
        mid_angle = (start_angle + end_angle) / 2 * 3.14159 / 180
        label_x = int(cx + (radius + 40) * __import__('math').cos(mid_angle))
        label_y = int(cy + (radius + 40) * __import__('math').sin(mid_angle))

        # Percentage
        pct = f"{proportion * 100:.1f}%"
        draw.text((label_x - len(pct) * 8, label_y - 15), pct, font=font, fill=(255, 255, 255))

        start_angle = end_angle

    # Legend below
    for i, (label, value) in enumerate(zip(labels, values)):
        x = cx - radius + i * 180
        color = _hex_to_rgb(colors[i % len(colors)])
        draw.rectangle([x, legend_y, x + 20, legend_y + 20], fill=color)
        draw.text((x + 30, legend_y), label, font=font, fill=(200, 200, 200))


def _render_scatter_chart(
    draw: ImageDraw.ImageDraw,
    labels: list[str],
    values: list[float],
    colors: list[str],
    left: int,
    top: int,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text_color: tuple[int, int, int],
) -> None:
    """Render a scatter chart."""
    if not values:
        return

    max_value = max(values) if values else 1
    min_value = min(values) if values else 0
    value_range = max_value - min_value if max_value != min_value else 1

    for i, value in enumerate(values):
        x = left + (i / max(len(values) - 1, 1)) * width
        y = top + height - int(((value - min_value) / value_range) * height)

        color = _hex_to_rgb(colors[i % len(colors)])
        dot_size = 20
        draw.ellipse([int(x - dot_size), int(y - dot_size), int(x + dot_size), int(y + dot_size)], fill=color)


def render_diagram(
    shot: Shot,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    background_color: str = "#0A1929",
    margin: int = 96,
) -> Path:
    """Render DiagramVisual to a PNG file.

    Uses Mermaid CLI if available, otherwise renders a fallback text diagram.
    """
    if not isinstance(shot.visual, DiagramVisual):
        raise TypeError(
            f"render_diagram only handles DiagramVisual, got {type(shot.visual).__name__}"
        )

    visual = shot.visual
    bg_rgb = _parse_hex_color(background_color)
    text_color = (255, 255, 255)
    sub_color = (200, 210, 225)
    tag_color = (120, 180, 220)

    image = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(image)

    tag_font = _load_font(40)
    title_font = _load_font(64)
    body_font = _load_font(48)
    code_font = _load_font(32)

    content_width = width - 2 * margin

    y = margin

    # Shot ID tag
    draw.text((margin, y), shot.shot_id, font=tag_font, fill=tag_color)
    y += int(40 * 1.6) + 24

    # Title from narration first line or visual title
    if visual.title:
        y = _draw_wrapped(draw, visual.title, title_font, margin, y, content_width, fill=text_color)
        y += 30

    # Try to render with Mermaid CLI
    mermaid_exe = _find_mermaid_cli()
    if mermaid_exe and visual.mermaid_code:
        try:
            svg_path = output_path.parent / f"{output_path.stem}_temp.svg"
            result = subprocess.run(
                [str(mermaid_exe), "-i", "-", "-o", str(svg_path)],
                input=visual.mermaid_code.encode(),
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and svg_path.exists():
                # Load and resize SVG to PNG
                from PIL import Image as PILImage
                svg_img = PILImage.open(svg_path)
                svg_img = svg_img.resize((width - 2 * margin, height - 400), PILImage.Resampling.LANCZOS)

                # Paste onto background
                bg_img = image.copy()
                bg_img.paste(svg_img, (margin, y))
                image = bg_img

                svg_path.unlink(missing_ok=True)
                logger.info("Mermaid diagram rendered successfully")

                draw = ImageDraw.Draw(image)
            else:
                logger.warning("Mermaid CLI failed, using fallback: %s", result.stderr.decode())
        except Exception as e:
            logger.warning("Mermaid rendering failed: %s", e)

    # Render fallback text diagram
    if not mermaid_exe or not visual.mermaid_code:
        y = _draw_wrapped(
            draw,
            "Diagram Preview",
            title_font,
            margin,
            y,
            content_width,
            fill=text_color,
        )
        y += 40

        # Draw a simple flowchart representation
        _draw_simple_flowchart(draw, visual.mermaid_code, margin, y, content_width, height - y - 300, body_font, sub_color)

    # Narration text at bottom
    narration_y = height - margin - 150
    _draw_wrapped(
        draw,
        shot.narration,
        body_font,
        margin,
        narration_y,
        content_width,
        fill=sub_color,
        line_spacing=1.5,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def _find_mermaid_cli() -> Optional[Path]:
    """Find Mermaid CLI executable."""
    candidates = [
        Path("mmdc"),  # npm global
        Path.home() / ".npm" / "mmdc",
        Path("/usr/local/bin/mmdc"),
        Path("/usr/bin/mmdc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
        # Check if it's in PATH
        try:
            result = subprocess.run(["which", "mmdc"], capture_output=True, text=True)
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
    return None


def _draw_simple_flowchart(
    draw: ImageDraw.ImageDraw,
    mermaid_code: str,
    x: int,
    y: int,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text_color: tuple[int, int, int],
) -> None:
    """Draw a simple representation of a flowchart from mermaid code."""
    if not mermaid_code:
        return

    # Parse simple mermaid graph LR
    lines = mermaid_code.strip().split("\n")
    nodes = []
    arrows = []

    # Simple parsing for graph LR TD
    for line in lines:
        line = line.strip()
        if "-->" in line:
            parts = line.split("-->")
            if len(parts) == 2:
                arrows.append((parts[0].strip(), parts[1].strip()))
        elif "[" in line:
            # Node definition like [text] or [text]
            m = __import__('re').search(r'\[(.+?)\]', line)
            if m:
                nodes.append(m.group(1))

    # Draw nodes
    node_height = 50
    node_width = 150
    gap = 40
    start_x = x + 50
    node_y = y + height // 2 - node_height // 2

    for i, node in enumerate(nodes):
        nx = start_x + i * (node_width + gap)
        draw.rounded_rectangle([nx, node_y, nx + node_width, node_y + node_height], radius=10, fill=(60, 80, 120))
        # Center text
        text_bbox = draw.textbbox((0, 0), node[:20], font=font)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text((nx + (node_width - text_width) // 2, node_y + 10), node[:20], font=font, fill=(255, 255, 255))

    # Draw arrows
    for src, dst in arrows:
        if src in nodes and dst in nodes:
            si = nodes.index(src)
            di = nodes.index(dst)
            sx = start_x + si * (node_width + gap) + node_width
            sy = node_y + node_height // 2
            dx = start_x + di * (node_width + gap)
            dy = sy
            draw.line([(sx, sy), (dx, dy)], fill=(120, 180, 220), width=3)


def render_image(
    shot: Shot,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    background_color: str = "#0A1929",
    margin: int = 96,
) -> Path:
    """Render ImageVisual to a PNG file.

    Loads image from path or URL, resizes to fit, and adds caption.
    """
    if not isinstance(shot.visual, ImageVisual):
        raise TypeError(
            f"render_image only handles ImageVisual, got {type(shot.visual).__name__}"
        )

    visual = shot.visual
    bg_rgb = _parse_hex_color(background_color)

    image = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(image)

    tag_font = _load_font(40)
    caption_font = _load_font(48)
    body_font = _load_font(48)

    content_width = width - 2 * margin

    y = margin

    # Shot ID tag
    draw.text((margin, y), shot.shot_id, font=tag_font, fill=(120, 180, 220))
    y += int(40 * 1.6) + 24

    # Load image
    try:
        from PIL import Image as PILImage
        import urllib.request

        if visual.path.startswith(("http://", "https://")):
            # Download from URL
            with urllib.request.urlopen(visual.path, timeout=10) as response:
                img = PILImage.open(response)
        else:
            # Load from local path
            img = PILImage.open(visual.path)

        # Resize to fit
        img_width, img_height = img.size
        scale = min((width - 2 * margin) / img_width, (height - 400) / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

        # Center on background
        paste_x = (width - new_width) // 2
        paste_y = y
        image.paste(img, (paste_x, paste_y))
        y = paste_y + new_height

    except Exception as e:
        logger.warning("Failed to load image %s: %s", visual.path, e)
        # Draw placeholder
        draw.rectangle([margin, y, width - margin, y + 400], fill=(60, 60, 60))
        draw.text((width // 2 - 100, y + 150), f"Image: {visual.path[:30]}...", font=caption_font, fill=(150, 150, 150))
        y += 450

    # Caption
    if visual.caption:
        y += 30
        y = _draw_wrapped(draw, visual.caption, caption_font, margin, y, content_width, fill=(200, 210, 225), line_spacing=1.3)

    # Narration text at bottom
    narration_y = height - margin - 150
    _draw_wrapped(
        draw,
        shot.narration,
        body_font,
        margin,
        narration_y,
        content_width,
        fill=(200, 210, 225),
        line_spacing=1.5,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def render_visual(
    shot: Shot,
    output_path: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    background_color: str = "#0A1929",
    **kwargs,
) -> Path:
    """Dispatch to the correct renderer based on visual type.

    This is the main entry point called from pipeline.py.
    """
    visual = shot.visual

    if isinstance(visual, TitleCardVisual):
        return render_title_card(shot, output_path, width, height, background_color, **kwargs)
    elif isinstance(visual, ChartVisual):
        return render_chart(shot, output_path, width, height, background_color, **kwargs)
    elif isinstance(visual, DiagramVisual):
        return render_diagram(shot, output_path, width, height, background_color, **kwargs)
    elif isinstance(visual, ImageVisual):
        return render_image(shot, output_path, width, height, background_color, **kwargs)
    else:
        raise TypeError(f"Unknown visual type: {type(visual).__name__}")