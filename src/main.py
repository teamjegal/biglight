"""클래스허브 — 독자 설계 LMS 데모.

로그인 화면에서 시작해 학생/교수 역할별로 다른 화면을 보여주는 학습관리시스템
데모다. 실제 서비스가 아니며 모든 데이터는 가상이다.

데이터는 Supabase 백엔드(``data.db``)에서 읽고 쓴다. 자격 증명이 없으면 가상 샘플
데이터를 메모리에 두고 같은 방식으로 동작한다(변경은 세션에만 남음).

실행:  streamlit run src/main.py
"""

from __future__ import annotations

import streamlit as st

import admin
import professor
import ui
from data import db
from data.sample import DEMO_LOGINS, STATUS_LABELS, TODAY
from ui import dday, dday_label, neg_date

st.set_page_config(page_title="클래스허브 LMS", page_icon="🎓", layout="wide")

# 학생용 좌측 네비게이션 — (페이지 이름, 아이콘). 순서가 메뉴 순서다.
NAV_ITEMS = [
    ("수강 강좌", "🏠"),
    ("대시보드", "📊"),
    ("공지사항", "📢"),
    ("강의 자료", "📄"),
    ("온라인 강의", "🎬"),
    ("과제 제출", "📝"),
    ("출석 확인", "✅"),
    ("성적 조회", "🏆"),
    ("시간표", "🗓️"),
    ("Q&A 게시판", "💬"),
]

ROLE_TABS = {"학생": "student", "교수": "professor", "관리자": "admin"}
ROLE_NAMES = {"student": "학생", "professor": "교수", "admin": "관리자"}
ID_LABELS = {"student": "학번", "professor": "사번", "admin": "관리자 ID"}


# ----------------------------------------------------------------------------
# 로그인 화면
# ----------------------------------------------------------------------------
def _attempt_login(login_id: str, password: str, role: str) -> None:
    """로그인을 시도하고, 성공하면 세션에 사용자를 저장한 뒤 다시 그린다."""
    try:
        user = db.login(login_id, password)
    except Exception:
        st.error("서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요.")
        return
    if user is None:
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        return
    if user["role"] != role:
        st.error(f"{ROLE_NAMES[role]} 계정이 아닙니다. 로그인 유형을 확인하세요.")
        return
    st.session_state.user = user
    st.rerun()


def _attempt_signup(login_id: str, name: str, department: str, password: str, confirm: str) -> None:
    """학생 회원가입을 시도하고, 성공하면 바로 로그인한다."""
    if password != confirm:
        st.error("비밀번호가 서로 다릅니다.")
        return
    try:
        db.signup_student(login_id, password, name, department)
        user = db.login(login_id, password)
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요.")
        return
    st.session_state.user = user
    st.rerun()


def _login_tab() -> None:
    tab = st.radio("로그인 유형", list(ROLE_TABS), horizontal=True)
    role = ROLE_TABS[tab]

    with st.form("login_form"):
        login_id = st.text_input(ID_LABELS[role])
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
    if submitted:
        _attempt_login(login_id, password, role)

    st.divider()
    st.caption("데모 계정으로 바로 둘러보기")
    c1, c2, c3 = st.columns(3)
    if c1.button("🎒 학생", use_container_width=True):
        _attempt_login(*DEMO_LOGINS["student"], "student")
    if c2.button("🧑‍🏫 교수", use_container_width=True):
        _attempt_login(*DEMO_LOGINS["professor"], "professor")
    if c3.button("🛠️ 관리자", use_container_width=True):
        _attempt_login(*DEMO_LOGINS["admin"], "admin")


def _signup_tab() -> None:
    st.caption("학생 회원가입입니다. 교수·관리자 계정은 관리자가 발급합니다.")
    with st.form("signup_form"):
        login_id = st.text_input("학번", key="su-id", help="숫자 6~12자리")
        name = st.text_input("이름", key="su-name")
        department = st.text_input("학과", key="su-dept")
        password = st.text_input(f"비밀번호 ({db.MIN_PASSWORD}자 이상)", type="password", key="su-pw")
        confirm = st.text_input("비밀번호 확인", type="password", key="su-pw2")
        submitted = st.form_submit_button("회원가입", type="primary", use_container_width=True)
    if submitted:
        _attempt_signup(login_id, name, department, password, confirm)


def login_page() -> None:
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown("## 🎓 클래스허브")
        st.caption("학습관리시스템 데모")

        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        with tab_login:
            _login_tab()
        with tab_signup:
            _signup_tab()

        if not db.is_connected():
            st.caption("🟠 샘플 데이터 모드(백엔드 미연결)")
        st.caption("⚠️ 데모 — 모든 데이터와 계정은 가상입니다.")


# ----------------------------------------------------------------------------
# 학생 화면 데이터
# ----------------------------------------------------------------------------
def load_student_state(user: dict) -> None:
    """학생 한 명의 화면 데이터를 백엔드에서 읽어 세션에 채운다(매 실행마다 새로)."""
    for key, value in db.load_student(user).items():
        st.session_state[key] = value


def _no_courses() -> bool:
    """수강 중인 강의가 없으면(갓 가입한 학생 등) 안내를 보여주고 True 를 돌려준다."""
    if st.session_state.courses:
        return False
    st.info("수강 중인 강의가 없습니다.")
    return True


def find_course(course_id: str) -> dict:
    return next(c for c in st.session_state.courses if c["id"] == course_id)


def all_assignments() -> list[dict]:
    """과목 정보를 붙인 전체 과제 목록."""
    rows = []
    for course in st.session_state.courses:
        for a in course["assignments"]:
            rows.append({**a, "course_id": course["id"], "course_title": course["title"]})
    return rows


# ----------------------------------------------------------------------------
# 출석률 계산
# ----------------------------------------------------------------------------
def attendance_rate(course_id: str) -> float:
    records = st.session_state.attendance.get(course_id, [])
    if not records:
        return 0.0
    # 출석 1.0, 지각 0.5, 결석 0.0 가중.
    weight = {"present": 1.0, "late": 0.5, "absent": 0.0}
    total = sum(weight[r["status"]] for r in records)
    return total / len(records) * 100


# ----------------------------------------------------------------------------
# 페이지: 대시보드
# ----------------------------------------------------------------------------
def page_dashboard() -> None:
    student = st.session_state.student
    st.title("대시보드")
    st.caption(f"{student['name']} 님, 반갑습니다. 오늘은 {TODAY:%m월 %d일}입니다.")

    assignments = all_assignments()
    pending = [a for a in assignments if a["status"] == "open"]
    upcoming = sorted(
        [a for a in pending if dday(a["due"]) >= 0], key=lambda a: a["due"]
    )
    overdue = [a for a in pending if dday(a["due"]) < 0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("수강 과목", f"{len(st.session_state.courses)}개")
    c2.metric("제출할 과제", f"{len(pending)}개")
    c3.metric("마감 지난 과제", f"{len(overdue)}개")
    courses = st.session_state.courses
    avg_rate = sum(attendance_rate(c["id"]) for c in courses) / len(courses) if courses else 0
    c4.metric("평균 출석률", f"{avg_rate:.0f}%")

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.subheader("📌 다가오는 과제 마감")
        if not upcoming:
            st.success("마감이 다가오는 과제가 없습니다.")
        for a in upcoming[:5]:
            n = dday(a["due"])
            emoji = "🔴" if n <= 2 else "🟡" if n <= 5 else "🟢"
            st.markdown(
                f"{emoji} **{a['title']}**  \n"
                f"{a['course_title']} · {a['due']:%m/%d} 마감 · **{dday_label(a['due'])}**"
            )
        if overdue:
            st.subheader("⏰ 마감 지난 미제출")
            for a in overdue:
                st.markdown(
                    f"🔴 **{a['title']}** — {a['course_title']} · {dday_label(a['due'])}"
                )

    with right:
        st.subheader("🗓️ 오늘의 수업")
        for course in st.session_state.courses:
            st.markdown(
                f"**{course['title']}**  \n"
                f"{course['schedule']} · {course['room']}  \n"
                f"교수: {course['professor']}"
            )
            st.caption("")


# ----------------------------------------------------------------------------
# 페이지: 강의 자료
# ----------------------------------------------------------------------------
def page_materials() -> None:
    st.title("강의 자료")
    st.caption("주차별 강의 자료를 열람합니다.")
    if _no_courses():
        return

    titles = {c["title"]: c["id"] for c in st.session_state.courses}
    chosen = st.selectbox("과목 선택", list(titles.keys()))
    course = find_course(titles[chosen])

    st.markdown(
        f"**{course['title']}** · {course['professor']} 교수 · {course['schedule']}"
    )
    st.divider()

    for m in sorted(course["materials"], key=lambda x: x["week"], reverse=True):
        col1, col2, col3 = st.columns([6, 2, 2])
        with col1:
            st.markdown(f"**{m['week']}주차 — {m['title']}**")
            st.caption(f"게시일: {m['posted']:%Y-%m-%d}")
        with col2:
            st.markdown(f"`{m['type']}` · {m['size_kb'] / 1024:.1f} MB")
        with col3:
            # 데모라 실제 파일은 없고, 열람 기록만 보여준다.
            if st.button("열람", key=f"view-{course['id']}-{m['id']}"):
                st.toast(f"{m['week']}주차 자료를 열었습니다. (데모)")
        st.divider()


# ----------------------------------------------------------------------------
# 페이지: 과제 제출
# ----------------------------------------------------------------------------
def page_assignments() -> None:
    st.title("과제 제출")
    st.caption("과제를 확인하고 파일을 제출합니다.")

    tab_open, tab_done = st.tabs(["제출할 과제", "제출·채점 내역"])

    with tab_open:
        rows = [a for a in all_assignments() if a["status"] == "open"]
        rows.sort(key=lambda a: a["due"])
        if not rows:
            st.success("제출할 과제가 없습니다. 👏")
        for a in rows:
            overdue = dday(a["due"]) < 0
            with st.expander(
                f"{'🔴' if overdue else '🟢'} {a['course_title']} — {a['title']}  "
                f"({dday_label(a['due'])})",
                expanded=False,
            ):
                st.markdown(
                    f"- 과목: **{a['course_title']}** ({a['course_id']})\n"
                    f"- 배점: **{a['points']}점**\n"
                    f"- 마감: **{a['due']:%Y-%m-%d}** · {dday_label(a['due'])}"
                )
                if overdue:
                    st.warning("마감이 지났습니다. 지각 제출로 처리됩니다.")
                st.file_uploader(
                    "제출 파일 (데모 — 실제 업로드되지 않음)",
                    key=f"file-{a['id']}",
                    type=["pdf", "zip", "docx", "py", "txt"],
                )
                if st.button("제출하기", key=f"submit-{a['id']}", type="primary"):
                    db.submit_assignment(st.session_state.user, a["id"], TODAY)
                    st.toast(f"'{a['title']}' 제출 완료!")
                    st.rerun()

    with tab_done:
        rows = [a for a in all_assignments() if a["status"] in ("submitted", "graded")]
        rows.sort(key=lambda a: a["due"], reverse=True)
        if not rows:
            st.info("아직 제출하거나 채점된 과제가 없습니다.")
        for a in rows:
            score = (
                f"{a['score']}/{a['points']}점"
                if a["status"] == "graded"
                else "채점 대기"
            )
            late = " · 지각 제출" if a.get("late") else ""
            st.markdown(
                f"**{a['course_title']} — {a['title']}**  \n"
                f"{STATUS_LABELS[a['status']]} · {score} · 마감 {a['due']:%m/%d}{late}"
            )
            st.divider()


# ----------------------------------------------------------------------------
# 페이지: 출석 확인
# ----------------------------------------------------------------------------
def page_attendance() -> None:
    st.title("출석 확인")
    st.caption("과목별 출석 현황을 확인하고, 오늘 수업 출석을 체크합니다.")

    for course in st.session_state.courses:
        records = st.session_state.attendance.get(course["id"], [])
        rate = attendance_rate(course["id"])

        with st.container(border=True):
            top1, top2 = st.columns([3, 1])
            with top1:
                st.markdown(f"**{course['title']}** · {course['professor']} 교수")
                st.caption(f"{course['schedule']} · {course['room']}")
            with top2:
                st.metric("출석률", f"{rate:.0f}%")

            # 주차별 상태 배지.
            badges = []
            for r in records:
                mark = {"present": "🟢", "late": "🟡", "absent": "🔴"}[r["status"]]
                badges.append(f"{r['week']}주 {mark}")
            st.markdown(" · ".join(badges) if badges else "_기록 없음_")

            next_week = (records[-1]["week"] + 1) if records else 1
            if st.button(
                f"{next_week}주차 출석 체크", key=f"attend-{course['id']}"
            ):
                db.check_attendance(st.session_state.user, course["id"], next_week, TODAY)
                st.toast(f"{course['title']} {next_week}주차 출석 완료!")
                st.rerun()


# ----------------------------------------------------------------------------
# 페이지: 수강 강좌 (카드 그리드 홈)
# ----------------------------------------------------------------------------
def page_my_courses() -> None:
    courses = st.session_state.courses
    student = st.session_state.student
    st.title("수강 강좌")
    st.caption(f"{student['semester']} · 수강 중인 강좌 {len(courses)}개")

    ui.course_cards(
        courses,
        st.session_state.card_colors,
        st.session_state.course_code,
        student["semester"],
        footer=lambda c: (c["professor"][:1], c["professor"]),
    )
    st.caption("강좌를 선택하려면 왼쪽 메뉴에서 강의 자료·과제·출석 등을 확인하세요.")


# ----------------------------------------------------------------------------
# 페이지: 공지사항
# ----------------------------------------------------------------------------
def page_announcements() -> None:
    st.title("공지사항")
    st.caption("전체 공지와 과목별 공지를 확인합니다.")

    course_name = {c["id"]: c["title"] for c in st.session_state.courses}
    options = ["전체"] + [c["title"] for c in st.session_state.courses]
    chosen = st.selectbox("범위", options)

    rows = list(st.session_state.announcements)
    if chosen != "전체":
        cid = next(c["id"] for c in st.session_state.courses if c["title"] == chosen)
        rows = [a for a in rows if a["course_id"] in (None, cid)]

    # 고정 공지 먼저, 그다음 최신순.
    rows.sort(key=lambda a: (not a["pinned"], neg_date(a["posted"])))
    for a in rows:
        scope = "전체" if a["course_id"] is None else course_name.get(a["course_id"], "")
        with st.container(border=True):
            head = "📌 " if a["pinned"] else ""
            st.markdown(f"{head}**{a['title']}**")
            st.caption(f"[{scope}] · {a['posted']:%Y-%m-%d}")
            st.write(a["body"])


# ----------------------------------------------------------------------------
# 페이지: 온라인 강의
# ----------------------------------------------------------------------------
def page_lectures() -> None:
    st.title("온라인 강의")
    st.caption("강의 영상 시청 진도를 확인하고 이어서 봅니다.")
    if _no_courses():
        return

    titles = {c["title"]: c["id"] for c in st.session_state.courses}
    chosen = st.selectbox("과목 선택", list(titles.keys()))
    cid = titles[chosen]
    videos = st.session_state.lectures.get(cid, [])

    done = sum(1 for v in videos if v["watched_pct"] == 100)
    overall = sum(v["watched_pct"] for v in videos) / len(videos) if videos else 0
    c1, c2 = st.columns(2)
    c1.metric("완료한 강의", f"{done}/{len(videos)}개")
    c2.metric("전체 진도율", f"{overall:.0f}%")
    st.divider()

    for v in videos:
        with st.container(border=True):
            top1, top2 = st.columns([5, 2])
            with top1:
                st.markdown(f"**{v['week']}주차 — {v['title']}**")
                st.caption(f"재생 시간 {v['duration_min']}분")
            with top2:
                label = (
                    "✅ 완료"
                    if v["watched_pct"] == 100
                    else ("▶ 이어보기" if v["watched_pct"] > 0 else "▶ 시청하기")
                )
                if st.button(label, key=f"watch-{cid}-{v['week']}"):
                    db.watch_lecture(st.session_state.user, v["id"])
                    st.toast(f"{v['week']}주차 강의 시청 완료!")
                    st.rerun()
            st.progress(v["watched_pct"] / 100, text=f"{v['watched_pct']}%")


# ----------------------------------------------------------------------------
# 페이지: 성적 조회
# ----------------------------------------------------------------------------
def page_grades() -> None:
    st.title("성적 조회")
    st.caption("과제와 시험 점수를 과목별로 확인합니다. (가채점 — 참고용)")

    for course in st.session_state.courses:
        graded = [a for a in course["assignments"] if a["status"] == "graded"]
        exams = st.session_state.exams.get(course["id"], [])

        got = sum(a["score"] for a in graded) + sum(e["score"] for e in exams)
        possible = sum(a["points"] for a in graded) + sum(e["max"] for e in exams)
        pct = (got / possible * 100) if possible else 0

        with st.container(border=True):
            top1, top2 = st.columns([3, 1])
            with top1:
                st.markdown(f"**{course['title']}** · {course['professor']} 교수")
            with top2:
                st.metric("환산 점수", f"{pct:.0f}%" if possible else "—")

            for a in graded:
                st.markdown(
                    f"- 과제 · {a['title']} — **{a['score']}/{a['points']}점**"
                )
            for e in exams:
                st.markdown(
                    f"- 시험 · {e['name']} — **{e['score']}/{e['max']}점** ({e['date']:%m/%d})"
                )
            if not graded and not exams:
                st.caption("아직 채점된 항목이 없습니다.")


# ----------------------------------------------------------------------------
# 페이지: Q&A 게시판
# ----------------------------------------------------------------------------
def page_qna() -> None:
    st.title("Q&A 게시판")
    st.caption("과목별로 질문을 올리고 답변을 확인합니다.")
    if _no_courses():
        return

    titles = {c["title"]: c["id"] for c in st.session_state.courses}
    chosen = st.selectbox("과목 선택", list(titles.keys()))
    cid = titles[chosen]

    with st.form("new_question", clear_on_submit=True):
        st.markdown("**새 질문 작성**")
        q_title = st.text_input("제목")
        q_body = st.text_area("내용")
        if st.form_submit_button("질문 등록", type="primary"):
            if q_title.strip():
                db.add_question(
                    st.session_state.user, cid, q_title.strip(), q_body.strip(), TODAY
                )
                st.toast("질문을 등록했습니다.")
                st.rerun()
            else:
                st.warning("제목을 입력하세요.")

    st.divider()
    posts = [q for q in st.session_state.qna if q["course_id"] == cid]
    posts.sort(key=lambda q: neg_date(q["posted"]))
    if not posts:
        st.info("아직 등록된 질문이 없습니다.")
    for q in posts:
        badge = "✅ 답변 완료" if q["answered"] else "🟡 답변 대기"
        with st.expander(f"{badge} · {q['title']}"):
            st.caption(f"{q['author']} · {q['posted']:%Y-%m-%d}")
            st.write(q["body"] or "_(내용 없음)_")
            for r in q["replies"]:
                st.markdown(f"> **{r['author']}**: {r['body']}")


def page_timetable() -> None:
    ui.timetable(st.session_state.courses)


STUDENT_PAGES = {
    "수강 강좌": page_my_courses,
    "대시보드": page_dashboard,
    "공지사항": page_announcements,
    "강의 자료": page_materials,
    "온라인 강의": page_lectures,
    "과제 제출": page_assignments,
    "출석 확인": page_attendance,
    "성적 조회": page_grades,
    "시간표": page_timetable,
    "Q&A 게시판": page_qna,
}


# ----------------------------------------------------------------------------
# 라우팅
# ----------------------------------------------------------------------------
def main() -> None:
    user = st.session_state.get("user")
    if not user:
        login_page()
        return

    role = user["role"]
    try:
        if role == "admin":
            admin.load(user)
        elif role == "professor":
            professor.load(user)
        else:
            load_student_state(user)
    except Exception as exc:
        st.error(f"데이터를 불러오지 못했습니다: {exc}")
        if st.button("다시 로그인"):
            ui.logout()
        st.stop()

    if role == "admin":
        admin.run()
        return
    if role == "professor":
        professor.run()
        return

    s = st.session_state.student
    page = ui.sidebar(
        NAV_ITEMS,
        s["name"],
        [f"{s['major']} · {s['student_id']}", s["semester"]],
        "학생",
    )
    STUDENT_PAGES[page]()


if __name__ == "__main__":
    main()
