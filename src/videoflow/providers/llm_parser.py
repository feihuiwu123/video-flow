"""LLM-powered Markdown → ShotList parser.

This module provides an async LLM parser that can replace the rule-based parser.
The signature intentionally matches the rule-based parser so callers can swap.

Usage:
    from videoflow.providers.llm_parser import parse_markdown_async

    # Async usage
    shotlist = await parse_markdown_async("# 标题\n内容...")

    # Sync wrapper
    shotlist = parse_markdown_sync("# 标题\n内容...")
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from videoflow.models import ShotList

if TYPE_CHECKING:
    from videoflow.providers import LLMProvider

_LOGGER = logging.getLogger(__name__)


def _shots_from_llm_json(llm_json: dict) -> dict:
    """Convert LLM output to ShotList-compatible JSON.

    Handles variations in LLM output format.
    """
    # Normalize shot structure
    shots = []

    # Handle nested shots array
    raw_shots = llm_json.get("shots", [])

    for i, shot in enumerate(raw_shots):
        normalized = {
            "shot_id": shot.get("shot_id", f"S{i+1:02d}"),
            "type": shot.get("type", "title_card"),
            "text": shot.get("text", shot.get("title", "")),
            "narration": shot.get("narration", shot.get("content", "")),
        }

        # Copy optional fields
        for key in ["visual", "emotion", "tips", "difficulty", "genre"]:
            if key in shot:
                normalized[key] = shot[key]

        shots.append(normalized)

    return {
        "title": llm_json.get("title", "Untitled"),
        "shots": shots,
    }


async def parse_markdown_async(
    markdown: str,
    provider_name: str = "deepseek",
    template: str | None = None,
) -> ShotList:
    """Parse Markdown into ShotList using LLM.

    Args:
        markdown: Input markdown text
        provider_name: LLM provider name (deepseek, openai, anthropic)
        template: Optional template-specific system prompt

    Returns:
        ShotList parsed from LLM response

    Raises:
        ValueError: If no LLM provider available or parsing fails
    """
    from videoflow.providers import get_llm_provider

    provider = get_llm_provider(provider_name)
    if provider is None:
        raise ValueError(
            f"No LLM provider available. "
            f"Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY. "
            f"Or use rule-based parser: videoflow.parser.parse_markdown()"
        )

    _LOGGER.info("Using LLM provider: %s", provider.name)

    # Call LLM
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: provider.parse(markdown, template)
    )

    # Handle errors
    if "error" in response:
        raise ValueError(f"LLM parsing failed: {response['error']}")

    # Normalize and convert to ShotList
    normalized = _shots_from_llm_json(response)

    # Import here to avoid circular dependency
    from videoflow.models import Shot, TitleCardVisual, Renderer

    shots = []
    cursor = 0.0

    for shot_data in normalized["shots"]:
        # Estimate duration based on narration length
        narration = shot_data.get("narration", "")
        duration = max(3.0, min(20.0, len(narration) / 3.5))

        shot = Shot(
            shot_id=shot_data.get("shot_id", f"S{len(shots)+1:02d}"),
            start=round(cursor, 3),
            end=round(cursor + duration, 3),
            narration=narration,
            visual=TitleCardVisual(
                text=shot_data.get("text", shot_data.get("title", "")),
                background="dark",
            ),
            renderer=Renderer.STATIC,
        )
        shots.append(shot)
        cursor += duration

    if not shots:
        raise ValueError("LLM returned no shots")

    return ShotList(shots=shots)


def parse_markdown_sync(
    markdown: str,
    provider_name: str = "deepseek",
    template: str | None = None,
) -> ShotList:
    """Synchronous wrapper for LLM parser."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    parse_markdown_async(markdown, provider_name, template)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                parse_markdown_async(markdown, provider_name, template)
            )
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(
            parse_markdown_async(markdown, provider_name, template)
        )


async def parse_file_async(
    path: Path | str,
    provider_name: str = "deepseek",
    template: str | None = None,
) -> ShotList:
    """Parse a markdown file using LLM."""
    text = Path(path).read_text(encoding="utf-8")
    return await parse_markdown_async(text, provider_name, template)


def parse_file(
    path: Path | str,
    provider_name: str = "deepseek",
    template: str | None = None,
) -> ShotList:
    """Synchronously parse a markdown file using LLM."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_markdown_sync(text, provider_name, template)
