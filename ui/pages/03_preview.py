"""Preview page - video preview and audio playback."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from videoflow import state
from videoflow.models import ShotList

st.set_page_config(page_title="预览 - Videoflow", page_icon="🎬", layout="wide")


def main():
    """Main page."""
    # Navigation
    col1, col2 = st.columns([1, 10])
    with col1:
        if st.button("← 返回"):
            st.switch_page("01_project_detail.py")
    with col2:
        st.header("🎬 预览")

    if "current_project" not in st.session_state or not st.session_state.current_project:
        st.warning("请先选择项目")
        if st.button("返回项目列表"):
            st.switch_page("../app.py")
        return

    project_id = st.session_state.current_project
    db_path = st.session_state.db_path
    project = state.get_project(db_path, project_id)

    if not project:
        st.error(f"项目 {project_id} 不存在")
        return

    workspace_dir = Path(project.workspace_dir)

    # Load shots
    shots_json = workspace_dir / "shots.json"
    if not shots_json.exists():
        st.error("未找到 shots.json")
        return

    shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))

    # Final video
    final_video = workspace_dir / "final.mp4"

    col_preview, col_shots = st.columns([2, 1])

    with col_preview:
        st.subheader("📹 终片预览")

        if final_video.exists():
            st.video(str(final_video))
            st.success(f"✅ 视频已生成: {final_video.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            st.warning("⏳ 视频尚未生成")
            st.info("运行 `video-agent resume {project_id}` 完成渲染")

    with col_shots:
        st.subheader("📋 镜头列表")

        for i, shot in enumerate(shotlist.shots):
            with st.expander(f"{shot.shot_id}: {shot.narration[:30]}..."):
                # Narration
                st.write(f"**旁白**: {shot.narration}")

                # Duration
                st.write(f"⏱️ {shot.duration:.1f}s")

                # Audio
                if shot.audio_file and Path(shot.audio_file).exists():
                    st.audio(str(shot.audio_file), format="audio/mp3")
                else:
                    st.text("🔇 无音频")

                # Visual
                if shot.visual_file and Path(shot.visual_file).exists():
                    st.image(str(shot.visual_file), width=200)
                else:
                    st.text("🖼️ 无视觉")

    st.markdown("---")

    # Shot timeline
    st.subheader("📊 时间线")

    total_duration = sum(s.duration for s in shotlist.shots)
    st.progress(1.0, text=f"总时长: {total_duration:.1f}秒, {len(shotlist.shots)} 个镜头")

    # Simple timeline visualization
    timeline_col = st.columns(len(shotlist.shots)) if len(shotlist.shots) <= 10 else st.columns(10)

    for i, shot in enumerate(shotlist.shots):
        with timeline_col[i % 10]:
            progress = shot.duration / total_duration if total_duration > 0 else 0
            st.metric(shot.shot_id, f"{shot.duration:.1f}s")
            st.progress(progress)

    # Actions
    st.markdown("---")
    col_re_render, col_review = st.columns(2)

    with col_re_render:
        if st.button("🔄 重新渲染", use_container_width=True):
            st.info("请使用 CLI 命令重新渲染: `video-agent resume`")

    with col_review:
        if st.button("📝 提交审核", use_container_width=True, type="primary"):
            st.switch_page("04_reviews.py")


if "db_path" not in st.session_state:
    st.switch_page("../app.py")

main()
