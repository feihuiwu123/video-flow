"""Pydantic v2 data models for the Videoflow demo.

Only the subset of the PRD's §4 schema that the minimum demo needs.
Other visual types (ChartVisual / DiagramVisual / StockFootageVisual …) are
kept as TODOs in ``TODO_LIST.md`` — this demo uses TitleCardVisual only.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Renderer(str, Enum):
    STATIC = "static"  # Solid background colour — the only renderer the demo ships.
    MERMAID = "mermaid"
    REMOTION = "remotion"
    PLAYWRIGHT = "playwright"


class TitleCardVisual(BaseModel):
    """A simple title card: solid background + optional headline text."""

    type: Literal["title_card"] = "title_card"
    text: str = Field(min_length=1, description="Headline text overlaid on the card.")
    background: Literal["dark", "light"] = "dark"
    highlight_keywords: list[str] = Field(default_factory=list)


class Shot(BaseModel):
    """One narration-bearing unit of video."""

    shot_id: str = Field(pattern=r"^S\d{2,3}$", description="e.g. S01, S02")
    start: float = Field(ge=0.0, description="Seconds since video start.")
    end: float = Field(ge=0.0, description="Seconds since video start.")
    narration: str = Field(min_length=1)
    visual: TitleCardVisual
    renderer: Renderer = Renderer.STATIC

    # Runtime-populated paths (empty at parse time, filled by TTS / renderer).
    audio_file: Optional[Path] = None
    visual_file: Optional[Path] = None
    tts_voice: Optional[str] = None

    @model_validator(mode="after")
    def _validate_time_window(self) -> "Shot":
        if self.end <= self.start:
            raise ValueError(
                f"Shot {self.shot_id}: end ({self.end}) must be greater than start ({self.start})"
            )
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class ShotList(BaseModel):
    """Ordered collection of shots with metadata for version compatibility."""

    version: Literal["1"] = "1"
    shots: list[Shot] = Field(min_length=1)
    style_preset: str = "default"
    actual_duration: Optional[float] = None

    @field_validator("shots")
    @classmethod
    def _unique_shot_ids(cls, shots: list[Shot]) -> list[Shot]:
        ids = [s.shot_id for s in shots]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate shot_id values are not allowed")
        return shots

    def retime_from_audio(self, durations: dict[str, float]) -> None:
        """Overwrite start/end timestamps using real TTS audio durations.

        Implements the PRD §5's "sound first, picture after" principle — picture
        timing follows the TTS output rather than the planner's guess.
        """
        cursor = 0.0
        for shot in self.shots:
            dur = durations.get(shot.shot_id)
            if dur is None:
                raise KeyError(f"Missing duration for {shot.shot_id}")
            shot.start = round(cursor, 3)
            shot.end = round(cursor + dur, 3)
            cursor += dur
        self.actual_duration = round(cursor, 3)


class ProjectStatus(str, Enum):
    CREATED = "created"
    PARSED = "parsed"
    TTS_DONE = "tts_done"
    RENDERED = "rendered"
    DONE = "done"
    FAILED = "failed"


class Project(BaseModel):
    """A single text-to-video task with persistent workspace."""

    project_id: str = Field(pattern=r"^proj_[a-z0-9]{6,}$")
    status: ProjectStatus = ProjectStatus.CREATED
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    workspace_dir: Path
    created_at: datetime = Field(default_factory=datetime.utcnow)
    shotlist: Optional[ShotList] = None

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def new(cls, workspace_root: Path, input_path: Optional[Path] = None) -> "Project":
        ts = datetime.utcnow().strftime("%y%m%d%H%M%S")
        pid = f"proj_{ts}"
        workspace = workspace_root / pid
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "audio").mkdir(exist_ok=True)
        (workspace / "scenes").mkdir(exist_ok=True)
        (workspace / "subtitles").mkdir(exist_ok=True)
        return cls(project_id=pid, workspace_dir=workspace, input_path=input_path)
