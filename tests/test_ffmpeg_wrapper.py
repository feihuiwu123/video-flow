"""Unit tests for videoflow.ffmpeg_wrapper — invocation shape only, no FFmpeg execution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from videoflow.ffmpeg_wrapper import (
    FFmpegError,
    RenderSpec,
    compose_scene,
    concat_scenes,
)


class TestRenderSpec:
    def test_defaults(self):
        spec = RenderSpec()
        assert spec.width == 1080
        assert spec.height == 1920
        assert spec.fps == 30
        assert spec.background_color.startswith("0x")


class TestComposeScene:
    def test_builds_expected_command(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"\x00")
        out = tmp_path / "o.mp4"

        captured: dict = {}

        def fake_run(cmd):
            captured["cmd"] = cmd
            out.write_bytes(b"\x00")

        with patch("videoflow.ffmpeg_wrapper._ensure_ffmpeg"), patch(
            "videoflow.ffmpeg_wrapper._run", side_effect=fake_run
        ):
            compose_scene(audio, out, duration=5.0)

        cmd = captured["cmd"]
        assert "ffmpeg" in cmd[0]
        # Has a colour source at the requested resolution / fps / duration.
        lavfi_arg = next(a for a in cmd if a.startswith("color="))
        assert "1080x1920" in lavfi_arg
        assert "r=30" in lavfi_arg
        assert "d=5.000" in lavfi_arg
        # Has audio input and shortest flag.
        assert str(audio) in cmd
        assert "-shortest" in cmd
        # Faststart for streaming.
        assert "+faststart" in cmd

    def test_visual_path_replaces_lavfi(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"\x00")
        visual = tmp_path / "frame.png"
        visual.write_bytes(b"\x00")
        out = tmp_path / "o.mp4"

        captured: dict = {}

        with patch("videoflow.ffmpeg_wrapper._ensure_ffmpeg"), patch(
            "videoflow.ffmpeg_wrapper._run", side_effect=lambda c: captured.setdefault("cmd", c)
        ):
            compose_scene(audio, out, duration=4.0, visual_path=visual)

        cmd = captured["cmd"]
        # No lavfi color source.
        assert not any(isinstance(a, str) and a.startswith("color=") for a in cmd)
        # Loop + duration + png input.
        assert "-loop" in cmd
        assert str(visual) in cmd
        # Scale/pad filter applied for aspect safety.
        vf_idx = cmd.index("-vf")
        vf = cmd[vf_idx + 1]
        assert "scale=" in vf
        assert "pad=" in vf

    def test_custom_spec_propagates(self, tmp_path):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"\x00")
        out = tmp_path / "o.mp4"
        spec = RenderSpec(width=720, height=1280, fps=24, background_color="0xFF00FF", crf=18)

        captured: dict = {}

        with patch("videoflow.ffmpeg_wrapper._ensure_ffmpeg"), patch(
            "videoflow.ffmpeg_wrapper._run", side_effect=lambda c: captured.setdefault("cmd", c)
        ):
            compose_scene(audio, out, duration=2.0, spec=spec)

        cmd = captured["cmd"]
        lavfi_arg = next(a for a in cmd if a.startswith("color="))
        assert "720x1280" in lavfi_arg
        assert "r=24" in lavfi_arg
        assert "c=0xFF00FF" in lavfi_arg
        assert "18" in cmd  # CRF value


class TestConcatScenes:
    def test_empty_list_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            concat_scenes([], tmp_path / "out.mp4")

    def test_writes_concat_file_with_abs_paths(self, tmp_path):
        scenes = [tmp_path / "s1.mp4", tmp_path / "s2.mp4"]
        for s in scenes:
            s.write_bytes(b"\x00")
        out = tmp_path / "final.mp4"

        captured: dict = {}

        def fake_run(cmd):
            # Capture the concat list file content before _run cleans up.
            list_file = Path(cmd[cmd.index("-i") + 1])
            captured["list"] = list_file.read_text(encoding="utf-8")
            captured["cmd"] = cmd
            out.write_bytes(b"\x00")

        with patch("videoflow.ffmpeg_wrapper._ensure_ffmpeg"), patch(
            "videoflow.ffmpeg_wrapper._run", side_effect=fake_run
        ):
            concat_scenes(scenes, out)

        assert "file '" in captured["list"]
        assert str(scenes[0].resolve()) in captured["list"]
        assert str(scenes[1].resolve()) in captured["list"]
        assert "-c" in captured["cmd"] and "copy" in captured["cmd"]


class TestFFmpegError:
    def test_subclass_of_runtime_error(self):
        assert issubclass(FFmpegError, RuntimeError)
