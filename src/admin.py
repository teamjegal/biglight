"""관리자 화면 — 교수 계정 생성, 강의 개설, 담당 교수 배정, 전체 현황.

교수 계정 생성은 DB 함수가 관리자 비밀번호를 호출마다 다시 검증한다(폼의
"관리자 비밀번호 확인"). 강의 개설·배정은 앱 계층에서 관리자 역할만 허용한다.
"""

from __future__ import annotations

import streamlit as st

import ui
from data import db

NAV_ITEMS = [
    ("대시보드", "📊"),
    ("교수 관리", "👥"),
    ("강의 관리", "📚"),
]


# ----------------------------------------------------------------------------
# 데이터 / 공통 헬퍼
# ----------------------------------------------------------------------------
def load(user: dict) -> None:
    """관리자 화면 데이터를 백엔드에서 읽어 세션에 채운다(매 실행마다 새로)."""
    st.session_state.adata = db.load_admin(user)


def _data() -> dict:
    return st.session_state.adata


def _user() -> dict:
    return st.session_state.user


def _do(action, *args, ok: str) -> bool:
    """쓰기 동작을 실행한다. 권한/입력 오류는 화면 메시지로 보여주고 False 를 돌려준다."""
    try:
        action(_user(), *args)
    except (db.PermissionDenied, ValueError) as exc:
        st.error(str(exc))
        return False
    st.toast(ok)
    return True


def _professor_options() -> dict[str, int]:
    return {f"{p['name']} ({p['login_id']})": p["id"] for p in _data()["professors"]}


# ----------------------------------------------------------------------------
# 페이지: 대시보드
# ----------------------------------------------------------------------------
def page_dashboard() -> None:
    st.title("대시보드")
    st.caption("전체 교수·강의 현황입니다.")

    s = _data()["stats"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("교수", f"{s['professors']}명")
    c2.metric("학생", f"{s['students']}명")
    c3.metric("강의", f"{s['courses']}개")
    c4.metric("강의 자료", f"{s['materials']}개")

    st.divider()
    st.subheader("강의 현황")
    st.table([
        {"강의": f"{c['title']} ({c['id']})", "담당 교수": c["professor"],
         "수강생": f"{c['students']}명", "자료": f"{c['materials']}개"}
        for c in _data()["courses"]
    ])


# ----------------------------------------------------------------------------
# 페이지: 교수 관리
# ----------------------------------------------------------------------------
def page_professors() -> None:
    st.title("교수 관리")
    st.caption("교수 계정을 만들고 현황을 확인합니다.")

    # 성공하면 번호를 올려 폼 위젯을 새로 만든다(실패 시에는 입력값이 남는다).
    n = st.session_state.get("_prof_form_n", 0)
    with st.form(f"new-prof-{n}"):
        st.markdown("**새 교수 계정**")
        c1, c2 = st.columns(2)
        login_id = c1.text_input("사번", key=f"prof-id-{n}", help="영문·숫자·-·_ 3~20자")
        name = c2.text_input("이름", key=f"prof-name-{n}")
        department = c1.text_input("학과", key=f"prof-dept-{n}")
        password = c2.text_input(f"초기 비밀번호 ({db.MIN_PASSWORD}자 이상)", type="password",
                                 key=f"prof-pw-{n}")
        admin_pw = st.text_input("관리자 비밀번호 확인", type="password", key=f"prof-admin-pw-{n}",
                                 help="계정 생성은 관리자 비밀번호를 서버에서 다시 확인합니다.")
        if st.form_submit_button("교수 계정 만들기", type="primary"):
            if _do(db.create_professor, admin_pw, login_id, password, name, department,
                   ok=f"교수 계정을 만들었습니다: {name.strip()}"):
                st.session_state["_prof_form_n"] = n + 1
                st.rerun()

    st.divider()
    st.subheader(f"교수 목록 ({len(_data()['professors'])}명)")
    st.table([
        {"사번": p["login_id"], "이름": p["name"], "학과": p["department"] or "—",
         "담당 강의": f"{p['courses']}개"}
        for p in _data()["professors"]
    ])


# ----------------------------------------------------------------------------
# 페이지: 강의 관리
# ----------------------------------------------------------------------------
def page_courses() -> None:
    st.title("강의 관리")
    st.caption("새 강의를 열고 담당 교수를 배정합니다.")
    options = _professor_options()
    if not options:
        st.warning("담당 교수로 배정할 교수 계정이 없습니다. 먼저 교수 계정을 만드세요.")
        return

    with st.expander("➕ 새 강의 개설", expanded=False):
        n = st.session_state.get("_course_form_n", 0)
        with st.form(f"new-course-{n}"):
            c1, c2 = st.columns(2)
            code = c1.text_input("강의 코드", key=f"course-code-{n}", help="예: CSE101")
            title = c2.text_input("강의명", key=f"course-title-{n}")
            prof_label = st.selectbox("담당 교수", list(options), key=f"course-prof-{n}")
            c3, c4 = st.columns(2)
            schedule = c3.text_input("강의 시간", key=f"course-sched-{n}", placeholder="월·수 10:00–11:15")
            room = c4.text_input("강의실", key=f"course-room-{n}")
            if st.form_submit_button("강의 개설", type="primary"):
                if _do(db.create_course, code, title, options[prof_label], schedule, room,
                       ok=f"강의를 개설했습니다: {title.strip()}"):
                    st.session_state["_course_form_n"] = n + 1
                    st.rerun()

    st.subheader(f"강의 목록 ({len(_data()['courses'])}개)")
    for c in _data()["courses"]:
        header = (f"{c['title']} ({c['id']}) · {c['professor']} · "
                  f"수강생 {c['students']}명 · 자료 {c['materials']}개")
        with st.expander(header):
            st.caption(f"{c['schedule'] or '시간 미정'} · {c['room'] or '강의실 미정'}")
            labels = list(options)
            current = next((i for i, pid in enumerate(options.values()) if pid == c["professor_id"]), 0)
            col1, col2 = st.columns([3, 1])
            choice = col1.selectbox("담당 교수", labels, index=current, key=f"assign-{c['id']}",
                                    label_visibility="collapsed")
            if col2.button("배정 변경", key=f"assign-btn-{c['id']}"):
                if options[choice] != c["professor_id"]:
                    if _do(db.assign_professor, c["id"], options[choice],
                           ok=f"{c['title']} 담당을 {choice.split(' (')[0]} 교수로 바꿨습니다."):
                        st.rerun()


PAGES = {
    "대시보드": page_dashboard,
    "교수 관리": page_professors,
    "강의 관리": page_courses,
}


def run() -> None:
    """관리자 사이드바를 그리고 선택된 페이지를 렌더링한다."""
    a = _data()["admin"]
    page = ui.sidebar(
        NAV_ITEMS,
        a["name"],
        [f"{a['department']} · {a['login_id']}", a["semester"]],
        "관리자",
    )
    PAGES[page]()
