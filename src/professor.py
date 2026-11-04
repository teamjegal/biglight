"""교수용 화면 — 담당 강의 관리, 공지·자료·과제 등록, 채점, 출석, Q&A 답변.

모든 쓰기는 ``data.db`` 의 권한 검사(담당 과목만 수정 가능)를 거친다. 권한 오류나
입력 오류는 예외 대신 화면의 오류 메시지로 보여준다.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

import ui
from data import db
from data.sample import TODAY
from ui import neg_date

NAV_ITEMS = [
    ("내 강의", "🏠"),
    ("대시보드", "📊"),
    ("공지 관리", "📢"),
    ("자료 관리", "📄"),
    ("과제·채점", "📝"),
    ("출석 관리", "✅"),
    ("Q&A 답변", "💬"),
    ("시간표", "🗓️"),
]

ATTENDANCE_LABELS = {"present": "출석", "late": "지각", "absent": "결석"}
ATTENDANCE_MARKS = {"present": "🟢", "late": "🟡", "absent": "🔴"}
ATTENDANCE_WEIGHT = {"present": 1.0, "late": 0.5, "absent": 0.0}
MATERIAL_TYPES = ["PDF", "슬라이드", "문서", "영상"]


# ----------------------------------------------------------------------------
# 데이터 / 공통 헬퍼
# ----------------------------------------------------------------------------
def load(user: dict) -> None:
    """교수의 관리 화면 데이터를 백엔드에서 읽어 세션에 채운다(매 실행마다 새로)."""
    st.session_state.pdata = db.load_professor(user)


def _data() -> dict:
    return st.session_state.pdata


def _user() -> dict:
    return st.session_state.user


def _pick(key: str) -> dict | None:
    """담당 강의 중 하나를 고르는 셀렉트박스. 강의가 없으면 None."""
    courses = _data()["courses"]
    if not courses:
        st.info("담당 강의가 없습니다.")
        return None
    labels = {f"{c['title']} ({c['id']})": c for c in courses}
    return labels[st.selectbox("강의 선택", list(labels), key=f"pick-{key}")]


def _do(action, *args, ok: str) -> None:
    """쓰기 동작을 실행하고, 성공하면 다시 그린다. 권한/입력 오류는 메시지로 보여준다."""
    try:
        action(_user(), *args)
    except (db.PermissionDenied, ValueError) as exc:
        st.error(str(exc))
        return
    st.toast(ok)
    st.rerun()


def _attendance_rate(course: dict) -> float:
    """강의 전체 수강생의 평균 출석률(출석 1, 지각 0.5, 결석 0)."""
    records = [s for per in _data()["attendance"][course["id"]].values() for s in per.values()]
    if not records:
        return 0.0
    return sum(ATTENDANCE_WEIGHT[s] for s in records) / len(records) * 100


# ----------------------------------------------------------------------------
# 페이지: 내 강의
# ----------------------------------------------------------------------------
def page_home() -> None:
    p = _data()["professor"]
    courses = _data()["courses"]
    st.title("내 강의")
    st.caption(f"{p['semester']} · 담당 강의 {len(courses)}개")
    ui.course_cards(
        courses,
        _data()["card_colors"],
        _data()["course_code"],
        p["semester"],
        footer=lambda c: ("👥", f"수강생 {len(c['roster'])}명"),
    )
    st.caption("왼쪽 메뉴에서 공지·자료·과제·출석을 관리하고 질문에 답변하세요.")


# ----------------------------------------------------------------------------
# 페이지: 대시보드
# ----------------------------------------------------------------------------
def page_dashboard() -> None:
    p = _data()["professor"]
    courses = _data()["courses"]
    st.title("대시보드")
    st.caption(f"{p['name']} 교수님, 반갑습니다. 오늘은 {TODAY:%m월 %d일}입니다.")

    students = {s["id"] for c in courses for s in c["roster"]}
    to_grade = sum(
        1 for c in courses for a in c["assignments"] for s in a["submissions"] if s["status"] == "submitted"
    )
    unanswered = [q for q in _data()["qna"] if not q["answered"]]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("담당 강의", f"{len(courses)}개")
    c2.metric("전체 수강생", f"{len(students)}명")
    c3.metric("채점 대기", f"{to_grade}건")
    c4.metric("답변 대기 질문", f"{len(unanswered)}건")

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.subheader("📝 과제 제출 현황")
        for c in courses:
            with st.container(border=True):
                st.markdown(f"**{c['title']}** · 수강생 {len(c['roster'])}명")
                if not c["assignments"]:
                    st.caption("출제한 과제가 없습니다.")
                for a in c["assignments"]:
                    done = len(a["submissions"])
                    total = done + len(a["missing"])
                    st.progress(
                        done / total if total else 0,
                        text=f"{a['title']} — 제출 {done}/{total} · 마감 {a['due']:%m/%d}",
                    )

    with right:
        st.subheader("✅ 강의별 평균 출석률")
        for c in courses:
            st.metric(c["title"], f"{_attendance_rate(c):.0f}%")
        st.subheader("💬 답변 대기 질문")
        if not unanswered:
            st.success("답변 대기 중인 질문이 없습니다.")
        names = {c["id"]: c["title"] for c in courses}
        for q in unanswered:
            st.markdown(f"🟡 **{q['title']}**  \n{names.get(q['course_id'], '')} · {q['author']}")


# ----------------------------------------------------------------------------
# 페이지: 공지 관리
# ----------------------------------------------------------------------------
def page_announcements() -> None:
    st.title("공지 관리")
    st.caption("담당 강의에 공지를 작성합니다.")
    course = _pick("ann")
    if course is None:
        return

    with st.form(f"new-ann-{course['id']}", clear_on_submit=True):
        st.markdown("**새 공지 작성**")
        title = st.text_input("제목")
        body = st.text_area("내용")
        pinned = st.checkbox("상단 고정")
        if st.form_submit_button("공지 등록", type="primary"):
            if title.strip():
                _do(db.post_announcement, course["id"], title.strip(), body.strip(), pinned, TODAY,
                    ok="공지를 등록했습니다.")
            else:
                st.warning("제목을 입력하세요.")

    st.divider()
    rows = [a for a in _data()["announcements"] if a["course_id"] == course["id"]]
    rows.sort(key=lambda a: (not a["pinned"], neg_date(a["posted"])))
    if not rows:
        st.info("등록된 공지가 없습니다.")
    for a in rows:
        with st.container(border=True):
            st.markdown(f"{'📌 ' if a['pinned'] else ''}**{a['title']}**")
            st.caption(f"{a['posted']:%Y-%m-%d}")
            st.write(a["body"])


# ----------------------------------------------------------------------------
# 페이지: 자료 관리
# ----------------------------------------------------------------------------
def page_materials() -> None:
    st.title("자료 관리")
    st.caption("주차별 강의 자료를 등록합니다.")
    course = _pick("mat")
    if course is None:
        return

    next_week = max((m["week"] for m in course["materials"]), default=0) + 1
    with st.form(f"new-mat-{course['id']}", clear_on_submit=True):
        st.markdown("**새 자료 등록**")
        c1, c2 = st.columns(2)
        week = c1.number_input("주차", min_value=1, max_value=16, value=min(next_week, 16))
        kind = c2.selectbox("형식", MATERIAL_TYPES)
        title = st.text_input("자료 제목")
        upload = st.file_uploader("파일 (데모 — 파일은 저장되지 않고 정보만 등록됩니다)")
        if st.form_submit_button("자료 등록", type="primary"):
            if title.strip():
                size_kb = max(1, len(upload.getvalue()) // 1024) if upload else 1024
                _do(db.add_material, course["id"], int(week), title.strip(), kind, size_kb, TODAY,
                    ok="자료를 등록했습니다.")
            else:
                st.warning("자료 제목을 입력하세요.")

    st.divider()
    if not course["materials"]:
        st.info("등록된 자료가 없습니다.")
    for m in sorted(course["materials"], key=lambda x: x["week"], reverse=True):
        st.markdown(f"**{m['week']}주차 — {m['title']}**  \n`{m['type']}` · "
                    f"{m['size_kb'] / 1024:.1f} MB · 게시일 {m['posted']:%Y-%m-%d}")
        st.divider()


# ----------------------------------------------------------------------------
# 페이지: 과제·채점
# ----------------------------------------------------------------------------
def page_assignments() -> None:
    st.title("과제·채점")
    st.caption("과제를 출제하고 제출물을 채점합니다.")
    course = _pick("asg")
    if course is None:
        return

    with st.expander("➕ 새 과제 출제"):
        with st.form(f"new-asg-{course['id']}", clear_on_submit=True):
            title = st.text_input("과제 제목")
            c1, c2 = st.columns(2)
            due = c1.date_input("마감일", value=TODAY + timedelta(days=7))
            points = c2.number_input("배점", min_value=1, max_value=100, value=20)
            if st.form_submit_button("출제", type="primary"):
                if title.strip():
                    _do(db.create_assignment, course["id"], title.strip(), due, int(points),
                        ok="과제를 출제했습니다.")
                else:
                    st.warning("과제 제목을 입력하세요.")

    if not course["assignments"]:
        st.info("출제한 과제가 없습니다.")
    for a in course["assignments"]:
        subs = a["submissions"]
        total = len(subs) + len(a["missing"])
        waiting = sum(1 for s in subs if s["status"] == "submitted")
        header = (f"{a['title']} · 마감 {a['due']:%m/%d} · {a['points']}점 · "
                  f"제출 {len(subs)}/{total} · 채점 대기 {waiting}")
        with st.expander(header):
            if not subs:
                st.info("아직 제출물이 없습니다.")
            for s in subs:
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                c1.markdown(f"**{s['student_name']}**  \n{s['login_id']}")
                late = " · 지각" if s["late"] else ""
                c2.caption(f"{s['submitted_at']:%m/%d} 제출{late}  \n"
                           f"{'채점 완료' if s['status'] == 'graded' else '채점 대기'}")
                score = c3.number_input(
                    "점수", min_value=0, max_value=a["points"], value=int(s["score"] or 0),
                    key=f"score-{s['id']}", label_visibility="collapsed",
                )
                if c4.button("점수 수정" if s["status"] == "graded" else "채점", key=f"grade-{s['id']}"):
                    _do(db.grade_submission, s["id"], int(score), ok=f"{s['student_name']} 채점 완료")
            if a["missing"]:
                st.caption("미제출: " + ", ".join(m["name"] for m in a["missing"]))


# ----------------------------------------------------------------------------
# 페이지: 출석 관리
# ----------------------------------------------------------------------------
def page_attendance() -> None:
    st.title("출석 관리")
    st.caption("주차별로 수강생 출석을 입력하고 현황을 확인합니다.")
    course = _pick("att")
    if course is None:
        return

    cid = course["id"]
    att = _data()["attendance"][cid]
    weeks_done = sorted({w for per in att.values() for w in per})
    next_week = (weeks_done[-1] + 1) if weeks_done else 1
    week = st.selectbox(
        "주차",
        list(range(1, next_week + 1)),
        index=next_week - 1,
        format_func=lambda w: f"{w}주차" + (" (새로 입력)" if w == next_week else ""),
        key=f"att-week-{cid}",
    )

    with st.form(f"att-form-{cid}-{week}"):
        picks = {}
        for s in course["roster"]:
            cur = att.get(s["id"], {}).get(week, "present")
            picks[s["id"]] = st.radio(
                f"{s['name']} ({s['login_id']})",
                list(ATTENDANCE_LABELS),
                index=list(ATTENDANCE_LABELS).index(cur),
                format_func=ATTENDANCE_LABELS.get,
                horizontal=True,
                key=f"att-{cid}-{week}-{s['id']}",
            )
        if st.form_submit_button(f"{week}주차 출석 저장", type="primary"):
            try:
                for student_id, status in picks.items():
                    db.set_attendance(_user(), cid, student_id, week, TODAY, status)
            except (db.PermissionDenied, ValueError) as exc:
                st.error(str(exc))
            else:
                st.toast(f"{week}주차 출석을 저장했습니다.")
                st.rerun()

    st.divider()
    st.subheader("출석 현황")
    if not weeks_done:
        st.info("아직 입력된 출석이 없습니다.")
        return
    rows = []
    for s in course["roster"]:
        per = att.get(s["id"], {})
        row = {"학생": s["name"]}
        for w in weeks_done:
            row[f"{w}주"] = ATTENDANCE_MARKS.get(per.get(w), "·")
        scored = [ATTENDANCE_WEIGHT[v] for v in per.values()]
        row["출석률"] = f"{sum(scored) / len(scored) * 100:.0f}%" if scored else "—"
        rows.append(row)
    st.table(rows)


# ----------------------------------------------------------------------------
# 페이지: Q&A 답변
# ----------------------------------------------------------------------------
def page_qna() -> None:
    st.title("Q&A 답변")
    st.caption("담당 강의에 올라온 질문에 답변합니다.")
    names = {c["id"]: c["title"] for c in _data()["courses"]}
    posts = sorted(_data()["qna"], key=lambda q: (q["answered"], -q["id"]))
    if not posts:
        st.info("아직 등록된 질문이 없습니다.")
    for q in posts:
        badge = "✅ 답변 완료" if q["answered"] else "🟡 답변 대기"
        with st.expander(f"{badge} · [{names.get(q['course_id'], '')}] {q['title']}"):
            st.caption(f"{q['author']} · {q['posted']:%Y-%m-%d}")
            st.write(q["body"] or "_(내용 없음)_")
            for r in q["replies"]:
                st.markdown(f"> **{r['author']}**: {r['body']}")
            with st.form(f"reply-form-{q['id']}", clear_on_submit=True):
                body = st.text_area("답변 작성", key=f"reply-{q['id']}")
                if st.form_submit_button("답변 등록", type="primary"):
                    if body.strip():
                        _do(db.answer_question, q["id"], body.strip(), ok="답변을 등록했습니다.")
                    else:
                        st.warning("답변 내용을 입력하세요.")


def page_timetable() -> None:
    ui.timetable(_data()["courses"])


PAGES = {
    "내 강의": page_home,
    "대시보드": page_dashboard,
    "공지 관리": page_announcements,
    "자료 관리": page_materials,
    "과제·채점": page_assignments,
    "출석 관리": page_attendance,
    "Q&A 답변": page_qna,
    "시간표": page_timetable,
}


def run() -> None:
    """교수 사이드바를 그리고 선택된 페이지를 렌더링한다."""
    p = _data()["professor"]
    page = ui.sidebar(
        NAV_ITEMS,
        f"{p['name']} 교수",
        [f"{p['department']} · {p['login_id']}", p["semester"]],
        "교수",
    )
    PAGES[page]()
