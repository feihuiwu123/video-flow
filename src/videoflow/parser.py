"""Rule-based Markdown → ShotList parser.

The PRD specifies a LangExtract + LLM planner. For the demo we ship a
deterministic rule-based parser so the happy path runs offline with zero
API keys. The signature intentionally matches a future async LLM parser so
callers (pipeline, CLI) can swap implementations without changes.

Supports visual blocks:
- :::chart ... ::: — generates ChartVisual
- ```mermaid ... ``` — generates DiagramVisual
- :::image path:::- generates ImageVisual
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from videoflow.models import (
    AnyVisual,
    ChartVisual,
    DiagramVisual,
    ImageVisual,
    Renderer,
    Shot,
    ShotList,
    TitleCardVisual,
)

# Rough guideline from PRD §5: Chinese ~= 3.5 chars/sec at default voice speed.
_CHARS_PER_SECOND = 3.5
_MIN_SHOT_SECONDS = 3.0
_MAX_SHOT_SECONDS = 20.0


def _estimate_duration(text: str) -> float:
    """Estimate narration length in seconds.

    This is only used at parse time; real durations are written back after
    TTS via :meth:`ShotList.retime_from_audio`.
    """
    chars = len(text)
    est = chars / _CHARS_PER_SECOND
    return max(_MIN_SHOT_SECONDS, min(_MAX_SHOT_SECONDS, est))


def _parse_chart_block(block_content: str) -> ChartVisual:
    """Parse :::chart block into ChartVisual.

    Block format:
    :::chart
    type: bar|line|pie|scatter
    title: Optional chart title
    data:
      labels: [item1, item2, ...]
      values: [10, 20, 30]
    color: #RRGGBB (optional)
    :::

    Also supports compact inline format:
    :::chart bar
    格力电器 1200
    中国平安 1431
    海螺水泥 800
    :::
    """
    lines = block_content.strip().split("\n")

    chart_type = "bar"
    title = None
    color_scheme = "default"
    data = {"labels": [], "values": []}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Handle inline format: "type data" on first line
        if i == 0 and line and not line.startswith("type:") and not line.startswith("title:") and not line.startswith("data:") and not line.startswith("color:"):
            parts = line.split()
            if parts:
                chart_type = parts[0].strip()
                i += 1
                # Parse remaining lines as label value pairs
                while i < len(lines):
                    data_line = lines[i].strip()
                    if data_line and data_line != ":::":
                        parts = data_line.split(None, 1)
                        if len(parts) >= 2:
                            data["labels"].append(parts[0])
                            try:
                                data["values"].append(float(parts[1]))
                            except ValueError:
                                pass
                        elif len(parts) == 1:
                            try:
                                val = float(parts[0])
                                data["values"].append(val)
                                data["labels"].append(f"Item {len(data['labels']) + 1}")
                            except ValueError:
                                pass
                    i += 1
                break

        if line.startswith("type:"):
            chart_type = line.split(":", 1)[1].strip()
        elif line.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("color:"):
            color_scheme = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            # Parse data section - look for key-value pairs or arrays
            j = i + 1
            labels = []
            values = []
            while j < len(lines):
                data_line = lines[j].strip()
                if not data_line or data_line == ":::":
                    break
                # Check for labeled array format: labels: [a, b, c]
                if ":" in data_line:
                    key, val = data_line.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    if key == "labels":
                        # Parse array [a, b, c]
                        if val.startswith("["):
                            inner = val[1:val.index("]")]
                            labels = [x.strip().strip("'\"") for x in inner.split(",")]
                    elif key == "values":
                        if val.startswith("["):
                            inner = val[1:val.index("]")]
                            values = [float(x.strip()) for x in inner.split(",") if x.strip()]
                else:
                    # Simple format: "label value" or just "value"
                    parts = data_line.split()
                    if len(parts) >= 2:
                        labels.append(parts[0])
                        try:
                            values.append(float(parts[1]))
                        except ValueError:
                            pass
                    elif len(parts) == 1:
                        try:
                            v = float(parts[0])
                            values.append(v)
                            if not labels:
                                labels.append(f"Item {len(values)}")
                        except ValueError:
                            pass
                j += 1
            data["labels"] = labels
            data["values"] = values
            i = j - 1
        i += 1

    return ChartVisual(
        chart_type=chart_type,
        data=data,
        title=title,
        color_scheme=color_scheme,
    )


def _parse_mermaid_block(block_content: str) -> DiagramVisual:
    """Parse ```mermaid block into DiagramVisual."""
    # Clean up the mermaid code
    mermaid_code = block_content.strip()
    return DiagramVisual(mermaid_code=mermaid_code)


def _parse_image_block(block_content: str) -> ImageVisual:
    """Parse :::image block into ImageVisual.

    Block format:
    :::image
    path: /path/to/image.jpg
    caption: Optional caption text
    background: dark|light|auto
    :::
    """
    lines = block_content.strip().split("\n")

    path = ""
    caption = None
    background = "auto"

    for line in lines:
        line = line.strip()
        if line.startswith("path:"):
            path = line.split(":", 1)[1].strip()
        elif line.startswith("caption:"):
            caption = line.split(":", 1)[1].strip()
        elif line.startswith("background:"):
            background = line.split(":", 1)[1].strip()

    return ImageVisual(path=path, caption=caption, background=background)


def _extract_visual_from_block(block_type: str, block_content: str) -> AnyVisual | None:
    """Extract visual spec from a visual block."""
    if block_type == "chart":
        return _parse_chart_block(block_content)
    elif block_type == "mermaid":
        return _parse_mermaid_block(block_content)
    elif block_type == "image":
        return _parse_image_block(block_content)
    return None


def _detect_visual_block(lines: list[str], start_idx: int) -> tuple[str | None, str, int]:
    """Detect visual blocks in markdown.

    Returns:
        (block_type, block_content, end_idx) or (None, "", start_idx) if no block found

    Supported block types:
    - :::chart - Chart data visualization
    - :::image - Image with optional caption
    - ```mermaid - Mermaid diagram
    """
    line = lines[start_idx].strip()

    # Check for :::block format
    chart_match = re.match(r"^:::chart\s*(.*)$", line)
    if chart_match:
        block_type = "chart"
        content_start = start_idx + 1
        # Find end marker :::
        end_idx = start_idx + 1
        while end_idx < len(lines):
            if lines[end_idx].strip() == ":::":
                break
            end_idx += 1
        content = "\n".join(line.strip() for line in lines[content_start:end_idx])
        return block_type, content, end_idx + 1

    # Check for :::image format
    image_match = re.match(r"^:::image\s*(.*)$", line)
    if image_match:
        block_type = "image"
        content_start = start_idx + 1
        end_idx = start_idx + 1
        while end_idx < len(lines):
            if lines[end_idx].strip() == ":::":
                break
            end_idx += 1
        # Check for inline format: :::image path:::
        inline_match = re.match(r"^:::image\s+(.+?)\s+:::", line)
        if inline_match:
            content = f"path: {inline_match.group(1)}"
        else:
            content = "\n".join(line.strip() for line in lines[content_start:end_idx])
        return block_type, content, end_idx + 1

    # Check for ```mermaid format
    if line.startswith("```mermaid"):
        block_type = "mermaid"
        content_start = start_idx + 1
        end_idx = start_idx + 1
        while end_idx < len(lines):
            if lines[end_idx].strip().startswith("```"):
                break
            end_idx += 1
        content = "\n".join(line for line in lines[content_start:end_idx])
        return block_type, content, end_idx + 1

    return None, "", start_idx


def _split_paragraphs(markdown: str) -> list[tuple[str, str, AnyVisual | None, Renderer]]:
    """Return a list of (heading, body, visual, renderer) tuples.

    Strategy:
    - Split on H1/H2/H3 headings.
    - Detect visual blocks (:::chart, :::image, ```mermaid) between sections.
    - Each section becomes a shot with optional visual content.

    Visual blocks are associated with the following shot.
    """
    lines = markdown.splitlines()
    sections: list[tuple[str, list[str], AnyVisual | None, Renderer]] = []
    current_heading = ""
    current_body: list[str] = []
    current_visual: AnyVisual | None = None
    current_renderer = Renderer.STATIC

    heading_re = re.compile(r"^\s*#{1,3}\s+(.+?)\s*$")

    i = 0
    while i < len(lines):
        raw_line = lines[i]

        # Check for visual blocks
        block_type, block_content, next_idx = _detect_visual_block(lines, i)
        if block_type is not None:
            visual = _extract_visual_from_block(block_type, block_content)
            if visual is not None:
                # Associate visual with current or next section
                if current_heading or current_body:
                    # Save current section with visual
                    sections.append((current_heading, current_body, visual, current_renderer))
                    current_heading = ""
                    current_body = []
                    current_visual = None
                    current_renderer = Renderer.STATIC
                else:
                    current_visual = visual
                    if block_type == "mermaid":
                        current_renderer = Renderer.MERMAID
            i = next_idx
            continue

        # Check for heading
        m = heading_re.match(raw_line)
        if m:
            if current_heading or current_body:
                sections.append((current_heading, current_body, current_visual, current_renderer))
                current_visual = None
                current_renderer = Renderer.STATIC
            current_heading = m.group(1).strip()
            current_body = []
        else:
            stripped = raw_line.strip()
            if stripped:
                current_body.append(stripped)

        i += 1

    if current_heading or current_body:
        sections.append((current_heading, current_body, current_visual, current_renderer))

    result: list[tuple[str, str, AnyVisual | None, Renderer]] = []
    for heading, body, visual, renderer in sections:
        body_text = " ".join(body).strip()
        if not body_text and not heading:
            continue
        if not heading:
            # Pull the first 20 chars of body as implicit title.
            heading = body_text[:20]
        if not body_text:
            body_text = heading
        result.append((heading, body_text, visual, renderer))

    return result


def parse_markdown(markdown: str) -> ShotList:
    """Turn a Markdown script into a ShotList.

    Supports visual blocks:
    - :::chart type: bar, data: [...], title: "..."
    - :::image path: /path/to/image.jpg, caption: "..."
    - ```mermaid ... ``` for diagrams

    Raises:
        ValueError: If the input produces zero shots.
    """
    sections = _split_paragraphs(markdown)
    if not sections:
        raise ValueError("Markdown input yielded zero usable sections")

    shots: list[Shot] = []
    cursor = 0.0
    for idx, (heading, body, visual, renderer) in enumerate(sections, start=1):
        duration = _estimate_duration(body)
        shot_id = f"S{idx:02d}"

        # Use detected visual or default to TitleCardVisual
        if visual is not None:
            shot_visual = visual
        else:
            shot_visual = TitleCardVisual(text=heading, background="dark")

        shot = Shot(
            shot_id=shot_id,
            start=round(cursor, 3),
            end=round(cursor + duration, 3),
            narration=body,
            visual=shot_visual,
            renderer=renderer,
        )
        shots.append(shot)
        cursor += duration

    return ShotList(shots=shots)


def parse_file(path: Path | str) -> ShotList:
    """Convenience: read a file and parse it."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_markdown(text)