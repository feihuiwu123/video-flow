"""Shot editor page - edit narration, visual specs, and timing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from videoflow import state
from videoflow.models import ShotList, Shot

st.set_page_config(page_title="Shot编辑器 - Videoflow", page_icon="✏️", layout="wide")


def load_shot(project_id: str, shot_id: str) -> tuple:
    """Load shot data."""
    db_path = st.session_state.db_path
    project = state.get_project(db_path, project_id)

    if not project:
        return None, None

    workspace_dir = Path(project.workspace_dir)
    shots_json = workspace_dir / "shots.json"

    if not shots_json.exists():
        return None, None

    shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))
    shot = next((s for s in shotlist.shots if s.shot_id == shot_id), None)

    return project, shot


def save_shot(project_id: str, shot_id: str, updated_shot: Shot) -> bool:
    """Save updated shot back to shots.json."""
    db_path = st.session_state.db_path
    project = state.get_project(db_path, project_id)

    if not project:
        return False

    workspace_dir = Path(project.workspace_dir)
    shots_json = workspace_dir / "shots.json"

    if not shots_json.exists():
        return False

    try:
        shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))

        # Update the shot
        for i, s in enumerate(shotlist.shots):
            if s.shot_id == shot_id:
                shotlist.shots[i] = updated_shot
                break

        # Save back
        shots_json.write_text(shotlist.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False


def main():
    """Main page."""
    # Navigation
    col1, col2 = st.columns([1, 10])
    with col1:
        if st.button("← 返回"):
            st.switch_page("01_project_detail.py")
    with col2:
        st.header("✏️ Shot 编辑器")

    if "current_project" not in st.session_state or not st.session_state.current_project:
        st.warning("请先选择项目")
        if st.button("返回项目列表"):
            st.switch_page("../app.py")
        return

    if "edit_shot_id" not in st.session_state or not st.session_state.edit_shot_id:
        st.warning("请先选择一个镜头")
        if st.button("返回项目详情"):
            st.switch_page("01_project_detail.py")
        return

    project_id = st.session_state.current_project
    shot_id = st.session_state.edit_shot_id

    project, shot = load_shot(project_id, shot_id)

    if not shot:
        st.error(f"未找到镜头 {shot_id}")
        return

    st.info(f"编辑项目 ** {project_id} ** 的镜头 ** {shot_id} **")

    # Create form
    with st.form("shot_editor"):
        st.subheader("📝 旁白文本")

        narration = st.text_area(
            "旁白内容",
            value=shot.narration,
            height=150,
            help="视频中要说的台词"
        )

        st.subheader("⏱️ 时间设置")

        col1, col2 = st.columns(2)
        with col1:
            duration = st.number_input(
                "时长(秒)",
                min_value=0.1,
                max_value=60.0,
                value=float(shot.duration),
                step=0.1,
            )
        with col2:
            start = st.number_input(
                "开始时间(秒)",
                min_value=0.0,
                value=float(shot.start),
                step=0.1,
            )

        end = start + duration

        st.subheader("🎨 视觉效果")

        visual_type = st.selectbox(
            "视觉类型",
            options=["title_card", "chart", "diagram", "stock_footage", "screen_capture", "image"],
            index=["title_card", "chart", "diagram", "stock_footage", "screen_capture", "image"].index(
                shot.visual.type if shot.visual else "title_card"
            ) if shot.visual else 0,
        )

        # Visual config editor (simplified JSON)
        visual_config = st.text_area(
            "视觉配置 (JSON)",
            value=json.dumps(shot.visual.config if shot.visual else {}, indent=2, ensure_ascii=False),
            height=100,
        )

        st.markdown("---")

        col_save, col_preview, col_cancel = st.columns(3)

        with col_save:
            submitted = st.form_submit_button("💾 保存修改", use_container_width=True, type="primary")

        with col_cancel:
            if st.form_submit_button("❌ 取消", use_container_width=True):
                st.switch_page("01_project_detail.py")

    if submitted:
        # Validate JSON
        try:
            visual_config_parsed = json.loads(visual_config) if visual_config.strip() else {}
        except json.JSONDecodeError as e:
            st.error(f"JSON 格式错误: {e}")
            return

        # Create updated shot
        from videoflow.models import VisualSpec, TitleCardVisual

        updated_visual = VisualSpec(
            type=visual_type,
            config=visual_config_parsed
        )

        updated_shot = Shot(
            shot_id=shot.shot_id,
            narration=narration,
            start=start,
            end=end,
            duration=duration,
            visual=updated_visual,
            audio_file=shot.audio_file,
            visual_file=shot.visual_file,
        )

        if save_shot(project_id, shot_id, updated_shot):
            st.success("✅ 保存成功!")
            st.balloons()
            if st.button("返回项目详情"):
                st.switch_page("01_project_detail.py")
        else:
            st.error("❌ 保存失败")


if "db_path" not in st.session_state:
    st.switch_page("../app.py")

main()
