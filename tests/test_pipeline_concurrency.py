"""Ensure ``render_all_scenes`` / ``render_all_visuals`` respect concurrency + preserve order."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

from videoflow.ffmpeg_wrapper import RenderSpec
from videoflow.models import Shot, ShotList, TitleCardVisual
from videoflow.pipeline import render_all_scenes, render_all_visuals


def _make_shotlist(n: int) -> ShotList:
    shots = []
    cursor = 0.0
    for i in range(1, n + 1):
        shots.append(
            Shot(
                shot_id=f"S{i:02d}",
                start=cursor,
                end=cursor + 1.0,
                narration=f"Narration {i}",
                visual=TitleCardVisual(text=f"Title {i}", background="dark"),
            )
        )
        cursor += 1.0
    return ShotList(shots=shots)


def test_scenes_parallel_observes_concurrency_limit(tmp_path: Path):
    """Run render_all_scenes with concurrency=3 and assert max observed
    in-flight calls respects that limit."""
    shotlist = _make_shotlist(6)
    # Attach fake audio + visuals so the asserts inside pass.
    for s in shotlist.shots:
        audio = tmp_path / "audio" / f"{s.shot_id}.mp3"
        visual = tmp_path / "vis" / f"{s.shot_id}.png"
        audio.parent.mkdir(parents=True, exist_ok=True)
        visual.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"mp3")
        visual.write_bytes(b"png")
        s.audio_file = audio
        s.visual_file = visual

    in_flight = 0
    max_seen = 0
    lock = threading.Lock()

    def fake_compose(audio_path, output_path, duration, visual_path, subtitle_path, spec):
        nonlocal in_flight, max_seen
        with lock:
            in_flight += 1
            max_seen = max(max_seen, in_flight)
        time.sleep(0.02)  # Give other threads time to pile in.
        output_path.write_bytes(b"fake mp4")
        with lock:
            in_flight -= 1

    spec = RenderSpec(width=1080, height=1920, fps=30, background_color="0x0A1929")
    with patch("videoflow.pipeline.compose_scene", side_effect=fake_compose):
        paths = render_all_scenes(
            shotlist,
            tmp_path / "scenes",
            subtitle_path=tmp_path / "unused.ass",
            spec=spec,
            max_concurrency=3,
        )

    assert [p.name for p in paths] == [f"{s.shot_id}.mp4" for s in shotlist.shots]
    assert max_seen <= 3
    # Given 6 shots and limit 3 we should see at least 2 concurrent at peak.
    assert max_seen >= 2


def test_visuals_parallel_preserves_order(tmp_path: Path):
    """render_all_visuals must attach visual_file to each shot regardless of
    thread completion order."""
    shotlist = _make_shotlist(4)
    spec = RenderSpec(width=1080, height=1920, fps=30, background_color="0x0A1929")

    def fake_render(shot, out, **_kwargs):
        out.parent.mkdir(parents=True, exist_ok=True)
        # Sleep longer for earlier shots so naive order-preservation would fail.
        idx = int(shot.shot_id[1:])
        time.sleep(0.01 * (5 - idx))
        out.write_bytes(b"PNG " + shot.shot_id.encode())

    with patch("videoflow.pipeline.render_title_card", side_effect=fake_render):
        render_all_visuals(shotlist, tmp_path / "visuals", spec, max_concurrency=4)

    for s in shotlist.shots:
        assert s.visual_file is not None
        assert s.visual_file.name == f"{s.shot_id}.png"
        assert s.visual_file.exists()


def test_scenes_sequential_when_concurrency_1(tmp_path: Path):
    """max_concurrency=1 should not spawn any thread pool."""
    shotlist = _make_shotlist(3)
    for s in shotlist.shots:
        audio = tmp_path / "audio" / f"{s.shot_id}.mp3"
        visual = tmp_path / "vis" / f"{s.shot_id}.png"
        audio.parent.mkdir(parents=True, exist_ok=True)
        visual.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"mp3")
        visual.write_bytes(b"png")
        s.audio_file = audio
        s.visual_file = visual

    seen_threads: set[int] = set()

    def fake_compose(audio_path, output_path, duration, visual_path, subtitle_path, spec):
        seen_threads.add(threading.get_ident())
        output_path.write_bytes(b"mp4")

    spec = RenderSpec(width=1080, height=1920, fps=30, background_color="0x0A1929")
    with patch("videoflow.pipeline.compose_scene", side_effect=fake_compose):
        render_all_scenes(shotlist, tmp_path / "scenes", tmp_path / "x.ass", spec,
                          max_concurrency=1)

    # All work ran on one thread when concurrency=1.
    assert len(seen_threads) == 1
