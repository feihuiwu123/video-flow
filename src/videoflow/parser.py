"""Rule-based Markdown → ShotList parser.

The PRD specifies a LangExtract + LLM planner. For the demo we ship a
deterministic rule-based parser so the happy path runs offline with zero
API keys. The signature intentionally matches a future async LLM parser so
callers (pipeline, CLI) can swap implementations without changes.
"""

from __future__ import annotations

import re
from pathlib import Path

from videoflow.models import Renderer, Shot, ShotList, TitleCardVisual

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


def _split_paragraphs(markdown: str) -> list[tuple[str, str]]:
    """Return a list of (heading, body) pairs.

    Strategy:
    - Split on H1/H2/H3 headings.
    - For each section, the body paragraphs are joined into narration.
    - Sections without a heading use the first line as the heading fallback.
    """
    lines = markdown.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_body: list[str] = []

    heading_re = re.compile(r"^\s*#{1,3}\s+(.+?)\s*$")

    for raw_line in lines:
        m = heading_re.match(raw_line)
        if m:
            if current_heading or current_body:
                sections.append((current_heading, current_body))
            current_heading = m.group(1).strip()
            current_body = []
        else:
            stripped = raw_line.strip()
            if stripped:
                current_body.append(stripped)

    if current_heading or current_body:
        sections.append((current_heading, current_body))

    result: list[tuple[str, str]] = []
    for heading, body in sections:
        body_text = " ".join(body).strip()
        if not body_text and not heading:
            continue
        if not heading:
            # Pull the first 20 chars of body as implicit title.
            heading = body_text[:20]
        if not body_text:
            body_text = heading
        result.append((heading, body_text))

    return result


def parse_markdown(markdown: str) -> ShotList:
    """Turn a Markdown script into a ShotList.

    Raises:
        ValueError: If the input produces zero shots.
    """
    sections = _split_paragraphs(markdown)
    if not sections:
        raise ValueError("Markdown input yielded zero usable sections")

    shots: list[Shot] = []
    cursor = 0.0
    for idx, (heading, body) in enumerate(sections, start=1):
        duration = _estimate_duration(body)
        shot_id = f"S{idx:02d}"
        shot = Shot(
            shot_id=shot_id,
            start=round(cursor, 3),
            end=round(cursor + duration, 3),
            narration=body,
            visual=TitleCardVisual(text=heading, background="dark"),
            renderer=Renderer.STATIC,
        )
        shots.append(shot)
        cursor += duration

    return ShotList(shots=shots)


def parse_file(path: Path | str) -> ShotList:
    """Convenience: read a file and parse it."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_markdown(text)
