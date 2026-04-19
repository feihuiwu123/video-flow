"""Provider system for LLM and TTS backends.

This module provides:
- LLM Provider abstraction for parsing Markdown -> ShotList
- TTS Provider abstraction (edge already exists, adding Azure/ElevenLabs)
- Base classes and registry for easy extension

Usage:
    from videoflow.providers import get_llm_provider, LLMProvider

    provider = get_llm_provider("deepseek")
    result = provider.parse("topic here")
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# LLM Provider Abstraction
# =============================================================================


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str = ""

    @abstractmethod
    def complete(self, prompt: str, system_prompt: str | None = None, **kwargs) -> LLMResponse:
        """Send a completion request to the LLM."""
        pass

    @abstractmethod
    def parse(self, markdown: str, template: str | None = None) -> dict[str, Any]:
        """Parse Markdown into ShotList JSON using LLM."""
        pass

    def _extract_json(self, content: str) -> dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        # Try to find raw JSON object
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        # Return as text if no JSON found
        return {"error": "No JSON found in response", "raw": content}


class LLMProviderRegistry:
    """Registry for LLM providers."""

    _providers: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        cls._providers[name] = provider_class
        _LOGGER.debug("Registered LLM provider: %s", name)

    @classmethod
    def get(cls, name: str) -> Optional[LLMProvider]:
        provider_class = cls._providers.get(name)
        if provider_class:
            return provider_class()
        return None

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._providers.keys())


def get_llm_provider(name: str | None = None) -> Optional[LLMProvider]:
    """Get an LLM provider by name."""
    if name is None:
        # Auto-detect based on available API keys
        if os.environ.get("DEEPSEEK_API_KEY"):
            name = "deepseek"
        elif os.environ.get("OPENAI_API_KEY"):
            name = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            name = "anthropic"
        else:
            return None

    return LLMProviderRegistry.get(name)


# =============================================================================
# DeepSeek Provider
# =============================================================================


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM provider using OpenAI-compatible API.

    API Reference: https://platform.deepseek.com/docs/api
    """

    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = base_url
        self.model = model

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")

    def complete(self, prompt: str, system_prompt: str | None = None, **kwargs) -> LLMResponse:
        """Send a completion request to DeepSeek."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def parse(self, markdown: str, template: str | None = None) -> dict[str, Any]:
        """Parse Markdown into ShotList JSON using DeepSeek."""
        system_prompt = """你是一个专业的视频脚本策划助手，擅长将主题转化为吸引人的短视频脚本。

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

        if template:
            # Template-specific system prompt override
            system_prompt = template

        prompt = f"""请为以下主题创作视频脚本：

{markdown}

请直接输出JSON格式的脚本，不要包含其他内容。"""

        response = self.complete(prompt, system_prompt)
        return self._extract_json(response.content)


# Register DeepSeek provider
LLMProviderRegistry.register("deepseek", DeepSeekProvider)


# =============================================================================
# OpenAI Provider (compatible with DeepSeek format)
# =============================================================================


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

    def complete(self, prompt: str, system_prompt: str | None = None, **kwargs) -> LLMResponse:
        """Send a completion request to OpenAI."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")

        client = OpenAI(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def parse(self, markdown: str, template: str | None = None) -> dict[str, Any]:
        """Parse Markdown into ShotList JSON using OpenAI."""
        # Use same prompt as DeepSeek
        provider = DeepSeekProvider(api_key=self.api_key)
        return provider.parse(markdown, template)


# Register OpenAI provider
LLMProviderRegistry.register("openai", OpenAIProvider)


# =============================================================================
# Anthropic Provider (using anthropic SDK)
# =============================================================================


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

    def complete(self, prompt: str, system_prompt: str | None = None, **kwargs) -> LLMResponse:
        """Send a completion request to Anthropic."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")

        client = Anthropic(api_key=self.api_key)

        response = client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 4096),
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
        )

        return LLMResponse(
            content=response.content[0].text if response.content else "",
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def parse(self, markdown: str, template: str | None = None) -> dict[str, Any]:
        """Parse Markdown into ShotList JSON using Anthropic."""
        # Use same prompt as DeepSeek
        system_prompt = """你是一个专业的视频脚本策划助手，擅长将主题转化为吸引人的短视频脚本。

你的任务是将用户给的主题拆分成多个镜头（shots），每个镜头包含：
1. 标题（吸引眼球的钩子）
2. 旁白（要说的台词，需要简洁有力）
3. 视觉类型建议

输出格式必须是有效的JSON：
{
  "title": "整体视频标题",
  "shots": [
    {"shot_id": "S01", "type": "title_card", "text": "标题", "narration": "旁白..."}
  ]
}

注意：每个镜头约8秒，至少4个镜头。"""

        if template:
            system_prompt = template

        prompt = f"""请为以下主题创作视频脚本（直接输出JSON）：

{markdown}"""

        response = self.complete(prompt, system_prompt)
        return self._extract_json(response.content)


# Register Anthropic provider
LLMProviderRegistry.register("anthropic", AnthropicProvider)


# =============================================================================
# TTS Provider Abstraction (M2)
# =============================================================================


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    name: str = ""

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path, **kwargs) -> dict[str, Any]:
        """Synthesize text to speech and save to file."""
        pass

    @abstractmethod
    def get_duration(self, audio_path: Path) -> float:
        """Get duration of audio file in seconds."""
        pass


class TTSProviderRegistry:
    """Registry for TTS providers."""

    _providers: dict[str, type[TTSProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[TTSProvider]) -> None:
        cls._providers[name] = provider_class

    @classmethod
    def get(cls, name: str) -> Optional[TTSProvider]:
        provider_class = cls._providers.get(name)
        if provider_class:
            return provider_class()
        return None

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._providers.keys())


# Edge TTS is already implemented in tts.py, Azure/ElevenLabs can be added here
# For now, we just provide the abstraction
