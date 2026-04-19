"""Unit tests for videoflow.config."""

from pathlib import Path

from videoflow.config import Config, load_config


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "does-not-exist.toml")
        assert isinstance(cfg, Config)
        assert cfg.rendering.width == 1080
        assert cfg.rendering.height == 1920
        assert cfg.tts.provider == "edge"

    def test_none_path_returns_defaults(self):
        cfg = load_config(None)
        assert cfg.subtitles.font_size == 56

    def test_overrides_from_toml(self, tmp_path):
        toml_path = tmp_path / "c.toml"
        toml_path.write_text(
            """
[runtime]
workspace_root = "/tmp/vf"
log_level = "DEBUG"

[rendering]
width = 720
height = 1280
fps = 24
background_color = "#FF00FF"

[tts]
voice = "en-US-GuyNeural"

[ffmpeg]
crf = 18

[subtitles]
font_size = 72
            """,
            encoding="utf-8",
        )
        cfg = load_config(toml_path)
        assert cfg.runtime.workspace_root == Path("/tmp/vf")
        assert cfg.runtime.log_level == "DEBUG"
        assert cfg.rendering.width == 720
        assert cfg.rendering.fps == 24
        assert cfg.rendering.background_color == "#FF00FF"
        assert cfg.tts.voice == "en-US-GuyNeural"
        assert cfg.ffmpeg.crf == 18
        assert cfg.subtitles.font_size == 72

    def test_unknown_keys_ignored(self, tmp_path):
        toml_path = tmp_path / "c.toml"
        toml_path.write_text(
            """
[unknown_section]
foo = "bar"

[rendering]
width = 1080
mystery = 42
            """,
            encoding="utf-8",
        )
        cfg = load_config(toml_path)
        assert cfg.rendering.width == 1080  # did not crash
