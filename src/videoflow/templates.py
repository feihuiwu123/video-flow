"""Template system for Videoflow.

This module provides a template registry for different video styles.
Templates contain:
- System prompts for parsing
- Visual style guidelines
- Narration tone/voice guidance

Usage:
    from videoflow.templates import get_template, list_templates

    tmpl = get_template("explainer")
    prompt = tmpl.get_parse_prompt("topic here")
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class TemplateConfig:
    """Configuration for a video template."""

    name: str
    display_name: str
    description: str
    # Visual settings
    background_color: str = "#0A1929"
    text_color: str = "#FFFFFF"
    highlight_color: str = "#FFD700"
    font_family: str = "Noto Sans SC"
    # Narration settings
    tone: str = "informative"  # informative, casual, formal, enthusiastic
    pace: str = "normal"  # slow, normal, fast
    # Parse settings
    default_duration_per_shot: float = 10.0  # seconds
    min_shots: int = 3
    max_shots: int = 20
    # Example usage
    example_topic: str = ""


@dataclass
class VideoTemplate(ABC):
    """Base class for video templates."""

    config: TemplateConfig

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for the LLM parser."""
        pass

    @abstractmethod
    def get_user_prompt(self, topic: str) -> str:
        """Return the user prompt for a given topic."""
        pass

    def get_visual_guidance(self) -> dict[str, Any]:
        """Return visual style guidance for the renderer."""
        return {
            "background_color": self.config.background_color,
            "text_color": self.config.text_color,
            "highlight_color": self.config.highlight_color,
            "font_family": self.config.font_family,
        }

    def get_narration_guidance(self) -> dict[str, str]:
        """Return narration style guidance."""
        return {
            "tone": self.config.tone,
            "pace": self.config.pace,
        }


# =============================================================================
# Template Implementations
# =============================================================================


class ExplainerTemplate(VideoTemplate):
    """Template for educational/explainer videos.

    Use case: Debunking myths, explaining concepts, teaching facts.
    Style: Clear, authoritative, engaging hooks.
    """

    def __init__(self):
        super().__init__(
            config=TemplateConfig(
                name="explainer",
                display_name="科普解说",
                description="用于科普解说、辟谣、知识讲解类视频",
                background_color="#0A1929",
                text_color="#FFFFFF",
                highlight_color="#FFD700",
                tone="informative",
                pace="normal",
                default_duration_per_shot=8.0,
                min_shots=4,
                max_shots=15,
                example_topic="股市反常识",
            )
        )

    def get_system_prompt(self) -> str:
        return """你是一个专业的视频脚本策划助手，擅长将主题转化为吸引人的短视频脚本。

你的任务是将用户给的主题拆分成多个镜头（shots），每个镜头包含：
1. 标题（吸引眼球的钩子）
2. 旁白（要说的台词，需要简洁有力）
3. 视觉类型建议

脚本风格要求：
- 开场要有"钩子"：用反常识/震惊/好奇的方式开头
- 中间层层递进：每个镜头只讲一个点
- 结尾要有总结或call-to-action

输出格式必须是有效的JSON，格式如下：
{
  "title": "整体视频标题",
  "shots": [
    {
      "shot_id": "S01",
      "type": "title_card",
      "text": "镜头标题",
      "narration": "旁白台词..."
    },
    ...
  ]
}

注意：
- 每个镜头时长约8秒
- 旁白要口语化、自然
- 标题要简洁有力
- 至少4个镜头，最多15个镜头"""

    def get_user_prompt(self, topic: str) -> str:
        return f"""请为以下主题创作一个科普视频脚本：

主题：{topic}

要求：
1. 开场用反常识或震惊点吸引观众
2. 中间内容要有逻辑递进
3. 结尾要有总结
4. 脚本要口语化，适合朗读

请直接输出JSON格式的脚本，不要包含其他内容。"""


class NewsDigestTemplate(VideoTemplate):
    """Template for news digest/recent events videos.

    Use case: Summarizing news, recent events, updates.
    Style: Brief, factual, structured.
    """

    def __init__(self):
        super().__init__(
            config=TemplateConfig(
                name="news_digest",
                display_name="新闻摘要",
                description="用于新闻摘要、事件盘点、资讯汇总类视频",
                background_color="#1A237E",
                text_color="#FFFFFF",
                highlight_color="#64FFDA",
                tone="formal",
                pace="fast",
                default_duration_per_shot=6.0,
                min_shots=5,
                max_shots=20,
                example_topic="本周科技要闻",
            )
        )

    def get_system_prompt(self) -> str:
        return """你是一个新闻摘要视频脚本策划助手。

你的任务是将新闻主题整理成简洁有力的短视频脚本。

脚本特点：
- 信息密度高，每句话都要有价值
- 结构清晰：标题 + 要点
- 时效性强
- 客观中立

输出格式：
{
  "title": "新闻标题",
  "date": "YYYY-MM-DD",
  "source": "来源",
  "shots": [
    {
      "shot_id": "S01",
      "type": "title_card",
      "text": "标题",
      "narration": "要点..."
    }
  ]
}

注意：
- 每个镜头约6秒
- 旁白要精炼
- 至少5个镜头"""

    def get_user_prompt(self, topic: str) -> str:
        return f"""请为以下主题创作新闻摘要视频脚本：

主题：{topic}

要求：
1. 信息密度要高，每句话都要有价值
2. 结构清晰：先标题，后要点
3. 时效性强
4. 客观中立

请直接输出JSON格式的脚本，不要包含其他内容。"""


class StoryTemplate(VideoTemplate):
    """Template for storytelling/narrative videos.

    Use case: Telling stories, case studies, anecdotes.
    Style: Engaging, emotional, narrative arc.
    """

    def __init__(self):
        super().__init__(
            config=TemplateConfig(
                name="story",
                display_name="故事叙述",
                description="用于讲故事、案例分享、人物特写类视频",
                background_color="#1B0A2E",
                text_color="#FFFFFF",
                highlight_color="#FF6B9D",
                tone="casual",
                pace="slow",
                default_duration_per_shot=12.0,
                min_shots=5,
                max_shots=12,
                example_topic="一个创业者的故事",
            )
        )

    def get_system_prompt(self) -> str:
        return """你是一个故事叙述视频脚本策划助手。

你的任务是将故事素材整理成有感染力的短视频脚本。

脚本特点：
- 有起承转合：开场、发展、高潮、结尾
- 情感共鸣强
- 细节描写丰富
- 留有悬念

输出格式：
{
  "title": "故事标题",
  "genre": "类型",
  "shots": [
    {
      "shot_id": "S01",
      "type": "title_card",
      "text": "标题",
      "narration": "旁白...",
      "emotion": "平静/紧张/感动等"
    }
  ]
}

注意：
- 每个镜头约12秒
- 旁白要有画面感
- 至少5个镜头"""

    def get_user_prompt(self, topic: str) -> str:
        return f"""请为以下主题创作故事叙述视频脚本：

主题：{topic}

要求：
1. 有起承转合：开场、发展、高潮、结尾
2. 情感共鸣强
3. 细节描写丰富
4. 留有悬念

请直接输出JSON格式的脚本，不要包含其他内容。"""


class TutorialTemplate(VideoTemplate):
    """Template for tutorial/how-to videos.

    Use case: Teaching skills, step-by-step guides.
    Style: Clear, practical, step-oriented.
    """

    def __init__(self):
        super().__init__(
            config=TemplateConfig(
                name="tutorial",
                display_name="教程指南",
                description="用于技能教学、步骤讲解、操作演示类视频",
                background_color="#004D40",
                text_color="#FFFFFF",
                highlight_color="#69F0AE",
                tone="informative",
                pace="normal",
                default_duration_per_shot=10.0,
                min_shots=4,
                max_shots=20,
                example_topic="如何做一杯手冲咖啡",
            )
        )

    def get_system_prompt(self) -> str:
        return """你是一个教程视频脚本策划助手。

你的任务是将技能或知识整理成易于学习的短视频脚本。

脚本特点：
- 步骤清晰
- 重点突出
- 实用性强
- 结尾有总结回顾

输出格式：
{
  "title": "教程标题",
  "difficulty": "初级/中级/高级",
  "shots": [
    {
      "shot_id": "S01",
      "type": "title_card",
      "text": "步骤标题",
      "narration": "操作说明...",
      "tips": "小贴士（非必须）"
    }
  ]
}

注意：
- 每个镜头约10秒
- 旁白要清晰易懂
- 至少4个镜头"""

    def get_user_prompt(self, topic: str) -> str:
        return f"""请为以下主题创作教程视频脚本：

主题：{topic}

要求：
1. 步骤要清晰
2. 重点要突出
3. 实用性强
4. 结尾要有总结回顾

请直接输出JSON格式的脚本，不要包含其他内容。"""


# =============================================================================
# Template Registry
# =============================================================================


class TemplateRegistry:
    """Registry for video templates."""

    _templates: dict[str, type[VideoTemplate]] = {
        "explainer": ExplainerTemplate,
        "news_digest": NewsDigestTemplate,
        "story": StoryTemplate,
        "tutorial": TutorialTemplate,
    }

    _custom_templates: dict[str, VideoTemplate] = {}

    @classmethod
    def register(cls, name: str, template: VideoTemplate) -> None:
        """Register a custom template."""
        cls._custom_templates[name] = template
        _LOGGER.info("Registered custom template: %s", name)

    @classmethod
    def get(cls, name: str) -> Optional[VideoTemplate]:
        """Get a template by name."""
        # Check custom templates first
        if name in cls._custom_templates:
            return cls._custom_templates[name]

        # Check built-in templates
        template_class = cls._templates.get(name)
        if template_class:
            return template_class()

        return None

    @classmethod
    def list(cls) -> list[TemplateConfig]:
        """List all available templates."""
        configs = []

        # Built-in templates
        for template_class in cls._templates.values():
            tmpl = template_class()
            configs.append(tmpl.config)

        # Custom templates
        for tmpl in cls._custom_templates.values():
            configs.append(tmpl.config)

        return configs

    @classmethod
    def load_from_dir(cls, templates_dir: Path) -> int:
        """Load custom templates from a directory.

        Templates should be JSON files with the template configuration.

        Args:
            templates_dir: Directory containing template JSON files.

        Returns:
            Number of templates loaded.
        """
        if not templates_dir.exists():
            _LOGGER.warning("Templates directory not found: %s", templates_dir)
            return 0

        loaded = 0
        for json_file in templates_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                config = TemplateConfig(**data)
                tmpl = _config_to_template(config)
                cls.register(config.name, tmpl)
                loaded += 1
            except Exception as e:
                _LOGGER.error("Failed to load template %s: %s", json_file, e)

        return loaded


def _config_to_template(config: TemplateConfig) -> VideoTemplate:
    """Convert a TemplateConfig to a generic VideoTemplate."""
    # For custom templates, we create a wrapper class
    class CustomTemplate(VideoTemplate):
        def __init__(self, cfg: TemplateConfig):
            super().__init__(cfg)

        def get_system_prompt(self) -> str:
            return self.config.__dict__.get(
                "system_prompt",
                "你是一个视频脚本策划助手。",
            )

        def get_user_prompt(self, topic: str) -> str:
            return f"请为以下主题创作视频脚本：\n\n主题：{topic}"

    return CustomTemplate(config)


def get_template(name: str) -> Optional[VideoTemplate]:
    """Get a template by name."""
    return TemplateRegistry.get(name)


def list_templates() -> list[TemplateConfig]:
    """List all available templates."""
    return TemplateRegistry.list()


def load_custom_templates(templates_dir: Optional[Path] = None) -> int:
    """Load custom templates from directory.

    Args:
        templates_dir: Directory containing templates.
                       Defaults to ./templates/

    Returns:
        Number of templates loaded.
    """
    if templates_dir is None:
        templates_dir = Path("templates")

    return TemplateRegistry.load_from_dir(templates_dir)
