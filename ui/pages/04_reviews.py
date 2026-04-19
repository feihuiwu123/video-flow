"""Reviews page - submit and view review records."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from videoflow import state
from videoflow.models import ShotList

st.set_page_config(page_title="审核记录 - Videoflow", page_icon="📝", layout="wide")


def submit_review(project_id: str, reviewer: str, status: str, comments: str) -> bool:
    """Submit a review record to the database."""
    db_path = st.session_state.db_path

    try:
        state.record_review(
            db_path,
            project_id=project_id,
            reviewer=reviewer,
            status=status,
            comments=comments,
        )
        return True
    except Exception as e:
        st.error(f"提交失败: {e}")
        return False


def load_reviews(project_id: str) -> list:
    """Load review records for a project."""
    db_path = st.session_state.db_path

    try:
        with state.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, project_id, reviewer, status, comments, created_at
                FROM reviews
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,),
            ).fetchall()
            return rows
    except Exception:
        return []


def main():
    """Main page."""
    # Navigation
    col1, col2 = st.columns([1, 10])
    with col1:
        if st.button("← 返回"):
            st.switch_page("03_preview.py")
    with col2:
        st.header("📝 审核记录")

    if "current_project" not in st.session_state or not st.session_state.current_project:
        st.warning("请先选择项目")
        if st.button("返回项目列表"):
            st.switch_page("../app.py")
        return

    project_id = st.session_state.current_project
    db_path = st.session_state.db_path

    # Tabs
    tab_submit, tab_history = st.tabs(["📤 提交审核", "📜 审核历史"])

    with tab_submit:
        st.subheader("提交审核意见")

        with st.form("review_form"):
            reviewer = st.text_input("审核人", value="", placeholder="输入你的名字")

            status = st.selectbox(
                "审核结果",
                options=["approved", "needs_revision", "rejected"],
                format_func=lambda x: {
                    "approved": "✅ 通过",
                    "needs_revision": "🔧 需要修改",
                    "rejected": "❌ 拒绝",
                }[x],
            )

            comments = st.text_area(
                "审核意见",
                value="",
                placeholder="输入具体的修改意见或备注...",
                height=150,
            )

            st.markdown("---")

            submitted = st.form_submit_button("📤 提交审核", use_container_width=True, type="primary")

        if submitted:
            if not reviewer.strip():
                st.warning("请输入审核人姓名")
            elif not comments.strip():
                st.warning("请输入审核意见")
            else:
                if submit_review(project_id, reviewer.strip(), status, comments.strip()):
                    st.success("✅ 审核已提交!")
                    st.balloons()
                else:
                    st.error("❌ 提交失败")

    with tab_history:
        st.subheader(f"项目 {project_id} 的审核历史")

        reviews = load_reviews(project_id)

        if not reviews:
            st.info("暂无审核记录")
        else:
            for review in reviews:
                review_id, proj_id, reviewer, rev_status, comments, created_at = review

                with st.container():
                    col1, col2, col3 = st.columns([1, 1, 3])

                    status_icons = {
                        "approved": "✅",
                        "needs_revision": "🔧",
                        "rejected": "❌",
                    }

                    with col1:
                        st.text(f"👤 {reviewer}")
                    with col2:
                        st.text(f"{status_icons.get(rev_status, '')} {rev_status}")
                    with col3:
                        st.text(f"📅 {created_at}")

                    st.write(comments)

                    st.divider()

    # Overall stats
    st.markdown("---")
    st.subheader("📊 审核统计")

    all_reviews = []
    try:
        with state.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT status FROM reviews WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            all_reviews = [r[0] for r in rows]
    except Exception:
        pass

    if all_reviews:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总审核次数", len(all_reviews))
        with col2:
            approved = sum(1 for r in all_reviews if r == "approved")
            st.metric("通过", approved)
        with col3:
            pending = sum(1 for r in all_reviews if r == "needs_revision")
            st.metric("待修改", pending)
    else:
        st.info("暂无审核数据")


if "db_path" not in st.session_state:
    st.switch_page("../app.py")

main()
