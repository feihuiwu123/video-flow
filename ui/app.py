"""Videoflow Streamlit UI - Project Review Dashboard.

This is an optional second channel for non-Claude Code users to review
and edit video projects. The UI reads from the SQLite state DB created
by M3.1.

Usage:
    video-agent ui          # CLI command (see cli.py)
    streamlit run app.py   # Direct run
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Page configuration
st.set_page_config(
    page_title="Videoflow",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import videoflow modules
try:
    from videoflow import state
    from videoflow.config import load_config
except ImportError as e:
    st.error(f"Failed to import videoflow: {e}")
    st.stop()


def get_db_path() -> Path:
    """Get the SQLite database path."""
    config_path = Path("config.toml")
    if config_path.exists():
        cfg = load_config(config_path)
        return state.default_db_path(cfg.runtime.workspace_root)
    return Path("workspace/videoflow.db")


def init_session_state():
    """Initialize Streamlit session state."""
    if "db_path" not in st.session_state:
        st.session_state.db_path = get_db_path()

    if "current_project" not in st.session_state:
        st.session_state.current_project = None


def render_sidebar():
    """Render the sidebar navigation."""
    with st.sidebar:
        st.title("🎬 Videoflow")
        st.markdown("---")

        # Database info
        db_path = st.session_state.db_path
        if db_path.exists():
            st.success("✅ 数据库已连接")
            st.caption(f"`{db_path}`")
        else:
            st.warning("⚠️ 数据库未找到")
            st.caption("运行 `video-agent init-db` 初始化")

        st.markdown("---")

        # Navigation
        st.page_link("app.py", label="📋 项目列表", icon="📋")
        st.page_link("pages/01_project_detail.py", label="🔍 项目详情", icon="🔍")
        st.page_link("pages/02_shot_editor.py", label="✏️ Shot 编辑器", icon="✏️")
        st.page_link("pages/03_preview.py", label="🎬 预览", icon="🎬")
        st.page_link("pages/04_reviews.py", label="📝 审核记录", icon="📝")

        st.markdown("---")

        # Quick actions
        if st.button("🔄 刷新数据", use_container_width=True):
            st.rerun()

        # Settings expander
        with st.expander("⚙️ 设置"):
            new_db_path = st.text_input(
                "数据库路径",
                value=str(st.session_state.db_path),
            )
            if new_db_path != str(st.session_state.db_path):
                st.session_state.db_path = Path(new_db_path)
                st.rerun()


def render_project_list():
    """Render the project list page."""
    st.header("📋 项目列表")
    st.markdown("所有视频项目的概览和状态")

    db_path = st.session_state.db_path

    if not db_path.exists():
        st.warning("数据库文件不存在，请先运行 `video-agent init-db`")
        return

    try:
        projects = state.list_projects(db_path, limit=100)
    except Exception as e:
        st.error(f"读取项目列表失败: {e}")
        return

    if not projects:
        st.info("暂无项目。运行 `video-agent generate` 创建第一个项目。")
        return

    # Stats row
    col1, col2, col3, col4 = st.columns(4)

    status_counts = {}
    for p in projects:
        status_counts[p.status] = status_counts.get(p.status, 0) + 1

    with col1:
        st.metric("总项目数", len(projects))
    with col2:
        st.metric("已完成", status_counts.get("done", 0))
    with col3:
        st.metric("进行中", status_counts.get("tts_done", 0) + status_counts.get("parsed", 0))
    with col4:
        st.metric("失败", status_counts.get("failed", 0))

    st.markdown("---")

    # Status filter
    filter_col, _ = st.columns([1, 3])
    with filter_col:
        status_filter = st.selectbox(
            "状态筛选",
            options=["全部", "created", "parsed", "tts_done", "rendered", "done", "failed"],
            index=0,
        )

    # Filter projects
    if status_filter != "全部":
        projects = [p for p in projects if p.status == status_filter]

    # Project cards
    for project in projects:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.subheader(f"🎬 {project.project_id}")
                st.caption(f"创建于: {project.created_at}")

                # Status badge
                status_colors = {
                    "created": "gray",
                    "parsed": "blue",
                    "tts_done": "orange",
                    "rendered": "purple",
                    "done": "green",
                    "failed": "red",
                }
                st.markdown(
                    f'<span style="background-color: {status_colors.get(project.status, "gray")}; '
                    f'color: white; padding: 4px 8px; border-radius: 4px;">'
                    f'{project.status.upper()}</span>',
                    unsafe_allow_html=True,
                )

            with col2:
                st.metric("镜头数", project.num_shots or "-")
                st.metric("时长(s)", f"{project.actual_duration:.1f}" if project.actual_duration else "-")

            with col3:
                if project.output_path:
                    st.caption("输出文件:")
                    st.code(project.output_path, language=None)

                if st.button("查看详情", key=f"view_{project.project_id}"):
                    st.session_state.current_project = project.project_id
                    st.switch_page("pages/01_project_detail.py")

            st.markdown("---")


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_project_list()


if __name__ == "__main__":
    main()
