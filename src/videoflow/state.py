"""SQLite thin wrapper — the project index, event log, and review queue.

Design intent (see TODO_LIST.md M3.1):

* **Filesystem is the truth source** for artifacts (shots.json, audio/, scenes/,
  final.mp4). The DB only tracks project metadata, the event stream, and
  review actions. If the DB is deleted, the video pipeline still runs —
  only ``list`` / ``status`` / ``resume`` / ``trace`` lose history.
* **Idempotent schema**: ``init_db()`` uses ``CREATE TABLE IF NOT EXISTS`` so
  callers may run it on every invocation without harm.
* **Stage readiness** is derived from the workspace layout, not from the DB.
  The DB records *what happened*, the filesystem answers *what exists now*.

Tables:

``projects``
    One row per ``video-agent generate`` invocation.

``events``
    Append-only log. ``stage`` is a free-form label (``parse``, ``tts``,
    ``render_visuals``, …). ``status`` is one of ``started`` / ``done`` /
    ``failed``. ``payload`` is JSON for structured context (durations,
    paths, error messages).

``reviews``
    Human-in-the-loop review actions produced by Skills or the Streamlit
    UI (M4). ``decision`` is ``approved`` / ``rejected`` / ``edited``.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

# Default location inside the workspace root. CLI subcommands resolve via
# ``Config.runtime.workspace_root`` then append this filename.
DB_FILENAME = "videoflow.db"


# --- Schema --------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id     TEXT PRIMARY KEY,
    status         TEXT NOT NULL DEFAULT 'created',
    input_path     TEXT,
    output_path    TEXT,
    workspace_dir  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    num_shots      INTEGER,
    actual_duration REAL
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    stage       TEXT NOT NULL,
    status      TEXT NOT NULL,
    ts          TEXT NOT NULL,
    payload     TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, id);
CREATE INDEX IF NOT EXISTS idx_events_stage ON events(project_id, stage);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    shot_id     TEXT,
    decision    TEXT NOT NULL,
    note        TEXT,
    ts          TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_project ON reviews(project_id, id);
"""


# --- Stage constants -----------------------------------------------------

# Free-form but centralised here so CLI / Skills / pipeline speak one
# vocabulary. New stages can be added as strings — the DB is schema-less
# on the stage column.
STAGE_PARSE = "parse"
STAGE_TTS = "tts"
STAGE_RENDER_VISUALS = "render_visuals"
STAGE_SUBTITLES = "subtitles"
STAGE_RENDER_SCENES = "render_scenes"
STAGE_FINALIZE = "finalize"

STAGES_ORDERED = (
    STAGE_PARSE,
    STAGE_TTS,
    STAGE_RENDER_VISUALS,
    STAGE_SUBTITLES,
    STAGE_RENDER_SCENES,
    STAGE_FINALIZE,
)

STATUS_STARTED = "started"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


# --- Data containers -----------------------------------------------------


@dataclass
class ProjectRow:
    project_id: str
    status: str
    input_path: Optional[str]
    output_path: Optional[str]
    workspace_dir: str
    created_at: str
    updated_at: str
    num_shots: Optional[int]
    actual_duration: Optional[float]


@dataclass
class EventRow:
    id: int
    project_id: str
    stage: str
    status: str
    ts: str
    payload: dict[str, Any]


@dataclass
class ReviewRow:
    id: int
    project_id: str
    shot_id: Optional[str]
    decision: str
    note: Optional[str]
    ts: str


# --- Helpers -------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_db_path(workspace_root: Path) -> Path:
    """Return the canonical DB path for a given workspace root."""
    return Path(workspace_root) / DB_FILENAME


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a connection with row factory + foreign keys on.

    Callers should always use this context manager so the connection is
    closed deterministically — important for tests that tmp-dir the DB.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Create the three tables if they are missing. Idempotent."""
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)


# --- Project CRUD --------------------------------------------------------


def upsert_project(
    db_path: Path,
    *,
    project_id: str,
    workspace_dir: Path,
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    status: str = "created",
    num_shots: Optional[int] = None,
    actual_duration: Optional[float] = None,
) -> None:
    """Create or update a project row. Safe to call repeatedly."""
    now = _utcnow()
    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT project_id FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO projects (
                    project_id, status, input_path, output_path,
                    workspace_dir, created_at, updated_at,
                    num_shots, actual_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    status,
                    str(input_path) if input_path else None,
                    str(output_path) if output_path else None,
                    str(workspace_dir),
                    now,
                    now,
                    num_shots,
                    actual_duration,
                ),
            )
        else:
            # COALESCE so callers can pass None to mean "leave alone".
            conn.execute(
                """
                UPDATE projects SET
                    status         = COALESCE(?, status),
                    input_path     = COALESCE(?, input_path),
                    output_path    = COALESCE(?, output_path),
                    workspace_dir  = COALESCE(?, workspace_dir),
                    num_shots      = COALESCE(?, num_shots),
                    actual_duration = COALESCE(?, actual_duration),
                    updated_at     = ?
                WHERE project_id = ?
                """,
                (
                    status,
                    str(input_path) if input_path else None,
                    str(output_path) if output_path else None,
                    str(workspace_dir),
                    num_shots,
                    actual_duration,
                    now,
                    project_id,
                ),
            )


def get_project(db_path: Path, project_id: str) -> Optional[ProjectRow]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    return _row_to_project(row) if row else None


def list_projects(
    db_path: Path,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[ProjectRow]:
    """Most-recent first. ``status`` filter is optional."""
    sql = "SELECT * FROM projects"
    params: tuple[Any, ...] = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params = params + (limit,)
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_project(r) for r in rows]


def _row_to_project(row: sqlite3.Row) -> ProjectRow:
    return ProjectRow(
        project_id=row["project_id"],
        status=row["status"],
        input_path=row["input_path"],
        output_path=row["output_path"],
        workspace_dir=row["workspace_dir"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        num_shots=row["num_shots"],
        actual_duration=row["actual_duration"],
    )


# --- Event log -----------------------------------------------------------


def record_event(
    db_path: Path,
    *,
    project_id: str,
    stage: str,
    status: str,
    payload: Optional[dict[str, Any]] = None,
) -> int:
    """Append one row to events. Returns the rowid."""
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO events (project_id, stage, status, ts, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                stage,
                status,
                _utcnow(),
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def list_events(
    db_path: Path,
    project_id: str,
    *,
    stage: Optional[str] = None,
    tail: Optional[int] = None,
) -> list[EventRow]:
    sql = "SELECT * FROM events WHERE project_id = ?"
    params: tuple[Any, ...] = (project_id,)
    if stage:
        sql += " AND stage = ?"
        params = params + (stage,)
    sql += " ORDER BY id ASC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    events = [_row_to_event(r) for r in rows]
    if tail is not None and tail > 0:
        events = events[-tail:]
    return events


def _row_to_event(row: sqlite3.Row) -> EventRow:
    try:
        payload = json.loads(row["payload"]) if row["payload"] else {}
    except json.JSONDecodeError:
        payload = {"_raw": row["payload"]}
    return EventRow(
        id=row["id"],
        project_id=row["project_id"],
        stage=row["stage"],
        status=row["status"],
        ts=row["ts"],
        payload=payload,
    )


# --- Reviews -------------------------------------------------------------


def record_review(
    db_path: Path,
    *,
    project_id: str,
    decision: str,
    shot_id: Optional[str] = None,
    note: Optional[str] = None,
) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO reviews (project_id, shot_id, decision, note, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, shot_id, decision, note, _utcnow()),
        )
        return int(cur.lastrowid)


def list_reviews(db_path: Path, project_id: str) -> list[ReviewRow]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE project_id = ? ORDER BY id ASC",
            (project_id,),
        ).fetchall()
    return [
        ReviewRow(
            id=r["id"],
            project_id=r["project_id"],
            shot_id=r["shot_id"],
            decision=r["decision"],
            note=r["note"],
            ts=r["ts"],
        )
        for r in rows
    ]


# --- Workspace-derived stage readiness -----------------------------------


def stage_readiness(workspace_dir: Path) -> dict[str, bool]:
    """Read the workspace layout and report which stages have artifacts.

    This is authoritative for ``status`` / ``resume``. The DB may lag behind
    the filesystem (e.g. pipeline crashed mid-stage before the ``done``
    event was written) — so resume trusts files, not events.
    """
    workspace_dir = Path(workspace_dir)
    shots_draft = workspace_dir / "shots_draft.json"
    shots_json = workspace_dir / "shots.json"

    parsed = shots_draft.exists() or shots_json.exists()

    # TTS done ⇔ every shot in the draft has an MP3. If no draft, we can't tell.
    tts_done = False
    shot_ids: list[str] = []
    source = shots_json if shots_json.exists() else shots_draft
    if source.exists():
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            shot_ids = [s["shot_id"] for s in data.get("shots", [])]
        except (json.JSONDecodeError, KeyError):
            shot_ids = []
    audio_dir = workspace_dir / "audio"
    if shot_ids and audio_dir.exists():
        tts_done = all((audio_dir / f"{sid}.mp3").exists() for sid in shot_ids)

    visuals_dir = workspace_dir / "visuals"
    visuals_done = bool(shot_ids) and visuals_dir.exists() and all(
        (visuals_dir / f"{sid}.png").exists() for sid in shot_ids
    )

    subtitles_done = (workspace_dir / "subtitles" / "final.ass").exists()

    scenes_dir = workspace_dir / "scenes"
    scenes_done = bool(shot_ids) and scenes_dir.exists() and all(
        (scenes_dir / f"{sid}.mp4").exists() for sid in shot_ids
    )

    finalized = any(workspace_dir.glob("*.mp4")) or (workspace_dir / "project.json").exists()

    return {
        STAGE_PARSE: parsed,
        STAGE_TTS: tts_done,
        STAGE_RENDER_VISUALS: visuals_done,
        STAGE_SUBTITLES: subtitles_done,
        STAGE_RENDER_SCENES: scenes_done,
        STAGE_FINALIZE: finalized,
    }


def next_stage(readiness: dict[str, bool]) -> Optional[str]:
    """First ordered stage that is not yet done. ``None`` if all done."""
    for stage in STAGES_ORDERED:
        if not readiness.get(stage, False):
            return stage
    return None


__all__ = [
    "DB_FILENAME",
    "ProjectRow",
    "EventRow",
    "ReviewRow",
    "STAGES_ORDERED",
    "STAGE_PARSE",
    "STAGE_TTS",
    "STAGE_RENDER_VISUALS",
    "STAGE_SUBTITLES",
    "STAGE_RENDER_SCENES",
    "STAGE_FINALIZE",
    "STATUS_STARTED",
    "STATUS_DONE",
    "STATUS_FAILED",
    "connect",
    "default_db_path",
    "get_project",
    "init_db",
    "list_events",
    "list_projects",
    "list_reviews",
    "next_stage",
    "record_event",
    "record_review",
    "stage_readiness",
    "upsert_project",
]
