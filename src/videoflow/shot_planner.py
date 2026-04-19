"""Professional shot planning module.

Generates structured shot-by-shot video scripts using LLM.
The output format follows professional video production standards.

Usage:
    from videoflow.shot_planner import plan_shots

    # Generate shot plan
    plan = await plan_shots("公司为什么上市分钱给陌生人", duration_hint=60)

    # Get structured shot list
    shotlist = plan.to_shotlist()
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

_LOGGER = logging.getLogger(__name__)


@dataclass
class ShotPlan:
    """One shot in the plan."""
    shot_id: str
    start: float
    end: float
    duration: float
    visual_type: str  # title_card, chart, diagram, image, etc.
    visual_title: str
    narration: str
    visual_data: Optional[dict] = None  # For charts: {"type": "bar", "data": {...}}
    key_points: list[str] = field(default_factory=list)
    subtitle_hint: str = ""

    @property
    def visual(self) -> dict:
        """Get visual spec as dict."""
        spec = {
            "type": self.visual_type,
            "title": self.visual_title,
        }
        if self.visual_data:
            spec.update(self.visual_data)
        return spec


@dataclass
class ShotPlanResult:
    """Complete shot plan result."""
    title: str
    total_duration: float
    style: str
    shots: list[ShotPlan]

    def to_shotlist(self) -> "ShotList":
        """Convert to ShotList model."""
        from videoflow.models import (
            Shot, ShotList, Renderer,
            TitleCardVisual, ChartVisual, DiagramVisual, ImageVisual,
        )

        shots = []
        cursor = 0.0

        for plan_shot in self.shots:
            # Create visual based on type
            if plan_shot.visual_type == "title_card":
                visual = TitleCardVisual(
                    text=plan_shot.visual_title or plan_shot.narration[:50],
                    background="dark",
                )
            elif plan_shot.visual_type == "chart":
                visual = ChartVisual(
                    chart_type=plan_shot.visual_data.get("chart_type", "bar") if plan_shot.visual_data else "bar",
                    data=plan_shot.visual_data.get("data", {}) if plan_shot.visual_data else {},
                    title=plan_shot.visual_title,
                )
            elif plan_shot.visual_type == "diagram":
                visual = DiagramVisual(
                    mermaid_code=plan_shot.visual_data.get("mermaid", "") if plan_shot.visual_data else "",
                    title=plan_shot.visual_title,
                )
            elif plan_shot.visual_type == "image":
                path = plan_shot.visual_data.get("path", "") if plan_shot.visual_data else ""
                if not path:
                    # Fallback to title_card if no path provided
                    visual = TitleCardVisual(
                        text=plan_shot.visual_title or plan_shot.narration[:50],
                        background="dark",
                    )
                else:
                    visual = ImageVisual(
                        path=path,
                        caption=plan_shot.visual_title,
                    )
            else:
                visual = TitleCardVisual(
                    text=plan_shot.narration[:50],
                    background="dark",
                )

            shot = Shot(
                shot_id=plan_shot.shot_id,
                start=round(cursor, 3),
                end=round(cursor + plan_shot.duration, 3),
                narration=plan_shot.narration,
                visual=visual,
                renderer=Renderer.STATIC,
            )
            shots.append(shot)
            cursor += plan_shot.duration

        return ShotList(shots=shots)

    def to_markdown(self) -> str:
        """Convert to markdown format for display."""
        lines = [
            f"# {self.title}",
            f"",
            f"**总时长**: {self.total_duration:.0f}秒",
            f"**风格**: {self.style}",
            f"",
            f"---",
            f"",
        ]

        for shot in self.shots:
            lines.append(f"### 【{shot.shot_id}】{shot.visual_title or '场景'}")
            lines.append(f"")
            lines.append(f"| 项目 | 内容 |")
            lines.append(f"|:---|:---|")
            lines.append(f"| 时长 | {shot.duration:.0f}秒 |")
            lines.append(f"| 画面 | {shot.visual_type} |")
            lines.append(f"| 画面内容 | {shot.visual_title or '-'} |")
            lines.append(f"| 口播 | {shot.narration[:60]}{'...' if len(shot.narration) > 60 else ''} |")
            if shot.key_points:
                lines.append(f"| 要点 | {', '.join(shot.key_points[:3])} |")
            lines.append(f"")

        return "\n".join(lines)

    def to_table_string(self) -> str:
        """Get a simple table string for CLI display."""
        lines = []
        for shot in self.shots:
            visual = f"[{shot.visual_type}] {shot.visual_title or '-'}"
            narration = shot.narration[:40] + ("..." if len(shot.narration) > 40 else "")
            lines.append(f"{shot.shot_id} | {shot.duration:.0f}s | {visual} | {narration}")
        return "\n".join(lines)


# System prompt for professional shot planning
SHOT_PLAN_SYSTEM_PROMPT = """你是一个专业的短视频分镜策划师，擅长将主题内容拆解为专业、吸引人的视频分镜脚本。

请严格按照以下JSON格式输出分镜脚本，不要输出任何其他内容：

{
  "title": "视频标题",
  "total_duration": 60,
  "style": "快节奏、信息密度高、反认知",
  "shots": [
    {
      "shot_id": "S01",
      "start": 0,
      "duration": 5,
      "visual_type": "title_card",
      "visual_title": "大字标题",
      "narration": "口播文案，控制在15-25字",
      "key_points": ["要点1", "要点2"],
      "subtitle_hint": "字幕提示"
    },
    {
      "shot_id": "S02",
      "duration": 8,
      "visual_type": "chart",
      "visual_title": "图表标题",
      "visual_data": {
        "chart_type": "bar",
        "data": {
          "labels": ["标签1", "标签2", "标签3"],
          "values": [100, 200, 150]
        }
      },
      "narration": "口播文案",
      "key_points": ["对比展示"]
    },
    {
      "shot_id": "S03",
      "duration": 10,
      "visual_type": "diagram",
      "visual_title": "流程图标题",
      "visual_data": {
        "mermaid": "graph LR\\n    A-->B\\n    B-->C"
      },
      "narration": "口播文案"
    }
  ]
}

分镜规则：
1. 总时长控制在45-90秒，符合短视频节奏
2. 每个镜头时长3-15秒，避免过长
3. 开头用悬念/反常识吸引眼球
4. 中间用数据/图表增强说服力
5. 结尾用金句/总结强化记忆
6. visual_type可选：title_card, chart, diagram, image
7. 数字和对比用图表(chart)
8. 流程/关系用流程图(diagram)
9. narration控制在15-25字，适合TTS朗读"""


async def plan_shots_async(
    content: str,
    provider_name: str = "deepseek",
    duration_hint: Optional[int] = None,
) -> ShotPlanResult:
    """Generate professional shot plan using LLM.

    Args:
        content: Topic or content to plan shots for
        provider_name: LLM provider (deepseek, openai, anthropic)
        duration_hint: Target duration in seconds (optional)

    Returns:
        ShotPlanResult with structured shot plans

    Raises:
        ValueError: If no LLM provider available
    """
    from videoflow.providers import get_llm_provider

    provider = get_llm_provider(provider_name)
    if provider is None:
        raise ValueError(
            "No LLM provider available. "
            "Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY."
        )

    _LOGGER.info("Planning shots with %s", provider.name)

    # Build user prompt
    user_prompt = f"请为以下内容策划专业短视频分镜脚本：\n\n{content}"
    if duration_hint:
        user_prompt += f"\n\n目标时长：{duration_hint}秒"

    # Call LLM
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: provider.complete(
            prompt=user_prompt,
            system_prompt=SHOT_PLAN_SYSTEM_PROMPT,
        )
    )

    # Extract content from response
    if hasattr(response, 'content'):
        content = response.content
    else:
        content = str(response)

    # Parse response
    try:
        # Find JSON in response
        import re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
            else:
                json_str = content

        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        _LOGGER.error("Failed to parse LLM response: %s", e)
        _LOGGER.error("Response was: %s", content[:500])
        raise ValueError(f"LLM response not valid JSON: {e}")

    if "error" in parsed:
        raise ValueError(f"LLM planning failed: {parsed['error']}")

    # Convert to ShotPlanResult
    title = parsed.get("title", "Untitled")
    total_duration = parsed.get("total_duration", 0)
    style = parsed.get("style", "")

    shots = []
    cursor = 0.0

    for shot_data in parsed.get("shots", []):
        duration = shot_data.get("duration", 5)
        shot = ShotPlan(
            shot_id=shot_data.get("shot_id", f"S{len(shots)+1:02d}"),
            start=cursor,
            end=cursor + duration,
            duration=duration,
            visual_type=shot_data.get("visual_type", "title_card"),
            visual_title=shot_data.get("visual_title", ""),
            visual_data=shot_data.get("visual_data"),
            narration=shot_data.get("narration", ""),
            key_points=shot_data.get("key_points", []),
            subtitle_hint=shot_data.get("subtitle_hint", ""),
        )
        shots.append(shot)
        cursor += duration

    return ShotPlanResult(
        title=title,
        total_duration=total_duration,
        style=style,
        shots=shots,
    )


def plan_shots(
    content: str,
    provider_name: str = "deepseek",
    duration_hint: Optional[int] = None,
) -> ShotPlanResult:
    """Synchronous wrapper for plan_shots_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    plan_shots_async(content, provider_name, duration_hint)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                plan_shots_async(content, provider_name, duration_hint)
            )
    except RuntimeError:
        return asyncio.run(
            plan_shots_async(content, provider_name, duration_hint)
        )
