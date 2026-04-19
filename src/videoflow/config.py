"""TOML configuration loader.

The full PRD config tree is large; the demo only reads the knobs it actually
honours. Unknown keys are ignored rather than rejected so future config files
remain forward-compatible.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — project requires 3.11+, kept for safety.
    import tomli as tomllib  # type: ignore


@dataclass
class RuntimeConfig:
    workspace_root: Path = Path("./workspace")
    log_level: str = "INFO"


@dataclass
class RenderingConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    background_color: str = "#0A1929"


@dataclass
class LLMConfig:
    """Configuration for LLM parsing (M2)."""

    # Provider: "none" (rule-based), "deepseek", "openai", "anthropic"
    provider: str = "none"

    # Model for each provider
    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Temperature for generation (0.0-1.0)
    temperature: float = 0.7

    # Max tokens per request
    max_tokens: int = 4096

    # Template name for prompt customization (optional)
    template: str | None = None


@dataclass
class TTSConfig:
    provider: str = "edge"
    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


@dataclass
class FFmpegConfig:
    preset: str = "medium"
    crf: int = 23
    audio_bitrate: str = "192k"


@dataclass
class SubtitleConfig:
    font_name: str = "PingFang SC"
    font_size: int = 56
    primary_color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    alignment: int = 2
    margin_v: int = 200


@dataclass
class AlignConfig:
    """Configuration for word-level subtitle alignment."""

    # Provider: "none" (per-shot), "mcp" (videoflow-align MCP server)
    provider: str = "none"

    # MCP server transport: "stdio" (default) or "sse" (localhost:8765)
    mcp_transport: str = "stdio"

    # faster-whisper model size (if using MCP)
    model_size: str = "base"

    # Language code or "auto"
    language: str = "auto"

    # Whether to emit word-level karaoke tags
    word_timestamps: bool = True


@dataclass
class CacheConfig:
    """On-disk content-addressable cache for TTS / visuals / stock footage (M7).

    ``enabled=False`` is the historical default — callers pay nothing for
    the feature until they opt in via ``config.toml``.
    """

    enabled: bool = False
    # Relative to workspace_root unless absolute.
    directory: str = "cache"


@dataclass
class PerformanceConfig:
    """Concurrency limits across pipeline stages (M7)."""

    # Parallel TTS synthesize calls. edge-tts is network-bound, so a few
    # concurrent calls help a lot but >8 rarely pays off.
    tts_concurrency: int = 4

    # Parallel Pillow visual renders. CPU-bound; default to CPU count at
    # runtime when <= 0.
    visuals_concurrency: int = 4

    # Parallel FFmpeg scene composes. Each subprocess uses multiple threads
    # internally — keep low to avoid over-subscription.
    scenes_concurrency: int = 2


@dataclass
class Config:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    rendering: RenderingConfig = field(default_factory=RenderingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    ffmpeg: FFmpegConfig = field(default_factory=FFmpegConfig)
    subtitles: SubtitleConfig = field(default_factory=SubtitleConfig)
    align: AlignConfig = field(default_factory=AlignConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)


def load_config(path: Path | str | None = None) -> Config:
    """Load ``config.toml`` from ``path`` (or return defaults if missing)."""
    if path is None:
        return Config()
    path = Path(path)
    if not path.exists():
        return Config()

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    cfg = Config()
    if "runtime" in data:
        cfg.runtime = RuntimeConfig(
            workspace_root=Path(
                data["runtime"].get("workspace_root", cfg.runtime.workspace_root)
            ),
            log_level=data["runtime"].get("log_level", cfg.runtime.log_level),
        )
    if "rendering" in data:
        r = data["rendering"]
        cfg.rendering = RenderingConfig(
            width=r.get("width", cfg.rendering.width),
            height=r.get("height", cfg.rendering.height),
            fps=r.get("fps", cfg.rendering.fps),
            background_color=r.get("background_color", cfg.rendering.background_color),
        )
    if "llm" in data:
        l = data["llm"]
        cfg.llm = LLMConfig(
            provider=l.get("provider", cfg.llm.provider),
            deepseek_model=l.get("deepseek_model", cfg.llm.deepseek_model),
            openai_model=l.get("openai_model", cfg.llm.openai_model),
            anthropic_model=l.get("anthropic_model", cfg.llm.anthropic_model),
            temperature=l.get("temperature", cfg.llm.temperature),
            max_tokens=l.get("max_tokens", cfg.llm.max_tokens),
            template=l.get("template", cfg.llm.template),
        )
    if "tts" in data:
        t = data["tts"]
        cfg.tts = TTSConfig(
            provider=t.get("provider", cfg.tts.provider),
            voice=t.get("voice", cfg.tts.voice),
            rate=t.get("rate", cfg.tts.rate),
            pitch=t.get("pitch", cfg.tts.pitch),
        )
    if "ffmpeg" in data:
        f = data["ffmpeg"]
        cfg.ffmpeg = FFmpegConfig(
            preset=f.get("preset", cfg.ffmpeg.preset),
            crf=f.get("crf", cfg.ffmpeg.crf),
            audio_bitrate=f.get("audio_bitrate", cfg.ffmpeg.audio_bitrate),
        )
    if "subtitles" in data:
        s = data["subtitles"]
        cfg.subtitles = SubtitleConfig(
            font_name=s.get("font_name", cfg.subtitles.font_name),
            font_size=s.get("font_size", cfg.subtitles.font_size),
            primary_color=s.get("primary_color", cfg.subtitles.primary_color),
            outline_color=s.get("outline_color", cfg.subtitles.outline_color),
            alignment=s.get("alignment", cfg.subtitles.alignment),
            margin_v=s.get("margin_v", cfg.subtitles.margin_v),
        )
    if "align" in data:
        a = data["align"]
        cfg.align = AlignConfig(
            provider=a.get("provider", cfg.align.provider),
            mcp_transport=a.get("mcp_transport", cfg.align.mcp_transport),
            model_size=a.get("model_size", cfg.align.model_size),
            language=a.get("language", cfg.align.language),
            word_timestamps=a.get("word_timestamps", cfg.align.word_timestamps),
        )
    if "cache" in data:
        c = data["cache"]
        cfg.cache = CacheConfig(
            enabled=c.get("enabled", cfg.cache.enabled),
            directory=c.get("directory", cfg.cache.directory),
        )
    if "performance" in data:
        p = data["performance"]
        cfg.performance = PerformanceConfig(
            tts_concurrency=p.get("tts_concurrency", cfg.performance.tts_concurrency),
            visuals_concurrency=p.get(
                "visuals_concurrency", cfg.performance.visuals_concurrency
            ),
            scenes_concurrency=p.get(
                "scenes_concurrency", cfg.performance.scenes_concurrency
            ),
        )
    return cfg
