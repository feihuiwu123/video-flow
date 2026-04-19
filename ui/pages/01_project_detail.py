"""Project detail page - shows shot list and project info."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from videoflow import state
from videoflow.models import ShotList

st.set_page_config(page_title="项目详情 - Videoflow", page_icon="🔍", layout="wide")


def render_sidebar():
    """Render minimal sidebar."""
    with st.sidebar:
        st.page_link("../app.py", label="← 返回项目列表")
        st.markdown("---")


def load_project(project_id: str) -> tuple:
    """Load project data from database and filesystem."""
    db_path = st.session_state.db_path

    # Get project from DB
    project = state.get_project(db_path, project_id)
    if not project:
        return None, None

    # Load shots.json
    workspace_dir = Path(project.workspace_dir)
    shots_json = workspace_dir / "shots.json"

    shotlist = None
    if shots_json.exists():
        try:
            shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))
        except Exception as e:
            st.warning(f"读取 shots.json 失败: {e}")

    return project, shotlist


def main():
    """Main page."""
    render_sidebar()

    if "current_project" not in st.session_state or not st.session_state.current_project:
        st.warning("请先从项目列表选择一个项目")
        if st.button("返回项目列表"):
            st.switch_page("../app.py")
        return

    project_id = st.session_state.current_project
    project, shotlist = load_project(project_id)

    if not project:
        st.error(f"项目 {project_id} 不存在")
        return

    # Header
    st.header(f"🔍 项目详情: {project_id}")

    # Project info cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("状态", project.status)
    with col2:
        st.metric("镜头数", project.num_shots or "-")
    with col3:
        st.metric("时长(s)", f"{project.actual_duration:.1f}" if project.actual_duration else "-")
    with col4:
        st.metric("创建时间", project.created_at)

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📋 镜头列表", "📁 文件结构", "📊 事件日志"])

    with tab1:
        if shotlist:
            st.subheader(f"共 {len(shotlist.shots)} 个镜头")

            # Shot table
            for i, shot in enumerate(shotlist.shots):
                with st.expander(f"**{shot.shot_id}**: {shot.narration[:50]}..."):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**旁白**: {shot.narration}")
                        st.write(f"**视觉类型**: {shot.visual.type if shot.visual else '无'}")
                    with col_b:
                        st.write(f"**时长**: {shot.duration:.2f}s")
                        st.write(f"**开始**: {shot.start:.2f}s")
                        st.write(f"**结束**: {shot.end:.2f}s")

                    # Audio and visual files
                    if shot.audio_file:
                        st.audio(str(shot.audio_file), format="audio/mp3")
                    if shot.visual_file:
                        st.image(str(shot.visual_file), width=300)

                    if st.button(f"编辑此镜头", key=f"edit_{shot.shot_id}"):
                        st.session_state.edit_shot_id = shot.shot_id
                        st.switch_page("02_shot_editor.py")
        else:
            st.info("未找到 shots.json 文件")

    with tab2:
        workspace_dir = Path(project.workspace_dir)
        st.subheader("文件结构")

        def list_files_recursive(path: Path, prefix: str = "") -> list:
            """List files recursively."""
            items = []
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith("."):
                        continue
                    if item.is_dir():
                        items.append(f"{prefix}📁 {item.name}/")
                        items.extend(list_files_recursive(item, prefix + "  "))
                    else:
                        size = item.stat().st_size
                        size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
                        items.append(f"{prefix}📄 {item.name} ({size_str})")
            except PermissionError:
                items.append(f"{prefix}⛔ 权限不足")
            return items

        if workspace_dir.exists():
            files = list_files_recursive(workspace_dir)
            for f in files[:50]:  # Limit to first 50 items
                st.text(f)
            if len(files) > 50:
                st.info(f"还有 {len(files) - 50} 个文件...")
        else:
            st.error("工作目录不存在")

    with tab3:
        events = state.list_events(st.session_state.db_path, project_id)
        if events:
            for e in events:
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    st.text(e.ts)
                with col2:
                    status_color = {"started": "blue", "done": "green", "failed": "red"}.get(e.status, "gray")
                    st.markdown(f'<span style="color:{status_color}">**{e.status}**</span>', unsafe_allow_html=True)
                with col3:
                    st.text(e.stage)
                if e.payload:
                    st.caption(str(e.payload))
                st.divider()
        else:
            st.info("暂无事件记录")


if "db_path" not in st.session_state:
    st.switch_page("../app.py")

main()
