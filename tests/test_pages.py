"""클래스허브 LMS 로그인·역할 분리 테스트.

CI/오프라인에서도 돌도록 네트워크를 쓰지 않는다. ``data.db._client`` 를 None 으로
패치해 항상 메모리(샘플) 백엔드로 실행하므로, 실제 Supabase 연결 없이도
로그인, 학생/교수 화면 렌더, 역할 간 데이터 흐름, 권한 검사를 검증할 수 있다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import data.db as db
import pytest
from data import sample
from streamlit.testing.v1 import AppTest

# AppTest 는 상대 경로를 호출 파일 기준으로 풀기에 절대 경로로 지정한다.
APP = str(Path(__file__).resolve().parents[1] / "src" / "main.py")

STUDENT_PAGES = [
    "수강 강좌", "대시보드", "공지사항", "강의 자료", "온라인 강의",
    "과제 제출", "출석 확인", "성적 조회", "시간표", "Q&A 게시판",
]
PROFESSOR_PAGES = [
    "내 강의", "대시보드", "공지 관리", "자료 관리", "과제·채점",
    "출석 관리", "Q&A 답변", "시간표",
]
STUDENT_BTN = "🎒 학생으로 시작"
PROFESSOR_BTN = "🧑‍🏫 교수로 시작"


# ---------------------------------------------------------------------------
# AppTest 헬퍼
# ---------------------------------------------------------------------------
def _app(monkeypatch) -> AppTest:
    """메모리 백엔드로 앱을 띄운다(로그인 화면에서 시작)."""
    monkeypatch.setattr(db, "_client", lambda: None)
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def _click(at: AppTest, label: str) -> AppTest:
    return next(b for b in at.button if b.label == label).click().run()


def _demo_login(at: AppTest, role: str) -> AppTest:
    return _click(at, STUDENT_BTN if role == "student" else PROFESSOR_BTN)


def _goto(at: AppTest, page: str) -> AppTest:
    option = next(o for o in at.radio[0].options if o.endswith(page))
    return at.radio[0].set_value(option).run()


def _form_login(at: AppTest, tab: str, login_id: str, password: str) -> AppTest:
    at.radio[0].set_value(tab).run()
    at.text_input[0].set_value(login_id)
    at.text_input[1].set_value(password)
    return _click(at, "로그인")


# ---------------------------------------------------------------------------
# 로그인
# ---------------------------------------------------------------------------
def test_starts_at_login_page(monkeypatch):
    at = _app(monkeypatch)
    assert not at.exception
    assert "user" not in at.session_state
    assert [t.label for t in at.text_input] == ["학번", "비밀번호"]


def test_professor_tab_asks_for_employee_id(monkeypatch):
    at = _app(monkeypatch)
    at.radio[0].set_value("교수").run()
    assert [t.label for t in at.text_input] == ["사번", "비밀번호"]


def test_wrong_password_is_rejected(monkeypatch):
    at = _form_login(_app(monkeypatch), "학생", "202512345", "wrong")
    assert "user" not in at.session_state
    assert any("올바르지 않습니다" in e.value for e in at.error)


def test_student_cannot_login_on_professor_tab(monkeypatch):
    pw = sample.DEMO_LOGINS["student"][1]
    at = _form_login(_app(monkeypatch), "교수", "202512345", pw)
    assert "user" not in at.session_state
    assert any("교수 계정이 아닙니다" in e.value for e in at.error)


def test_form_login_succeeds_with_correct_credentials(monkeypatch):
    login_id, pw = sample.DEMO_LOGINS["professor"]
    at = _form_login(_app(monkeypatch), "교수", login_id, pw)
    assert at.session_state["user"]["role"] == "professor"
    assert not at.exception


def test_logout_returns_to_login(monkeypatch):
    at = _demo_login(_app(monkeypatch), "student")
    assert at.session_state["user"]["role"] == "student"
    at = _click(at, "로그아웃")
    assert "user" not in at.session_state
    assert [t.label for t in at.text_input] == ["학번", "비밀번호"]


# ---------------------------------------------------------------------------
# 역할별 화면
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", STUDENT_PAGES)
def test_student_page_renders(monkeypatch, page):
    at = _goto(_demo_login(_app(monkeypatch), "student"), page)
    assert not at.exception, f"학생 {page} 페이지 예외"


@pytest.mark.parametrize("page", PROFESSOR_PAGES)
def test_professor_page_renders(monkeypatch, page):
    at = _goto(_demo_login(_app(monkeypatch), "professor"), page)
    assert not at.exception, f"교수 {page} 페이지 예외"


def test_menus_differ_by_role(monkeypatch):
    student = _demo_login(_app(monkeypatch), "student")
    student_menu = {o.split(" ", 1)[1] for o in student.radio[0].options}
    professor = _demo_login(_app(monkeypatch), "professor")
    professor_menu = {o.split(" ", 1)[1] for o in professor.radio[0].options}
    assert "과제 제출" in student_menu and "과제·채점" not in student_menu
    assert "과제·채점" in professor_menu and "과제 제출" not in professor_menu


def test_student_sees_only_enrolled_courses(monkeypatch):
    at = _demo_login(_app(monkeypatch), "student")
    assert [c["id"] for c in at.session_state["courses"]] == ["CSE311", "CSE245", "GEN102"]


def test_professor_sees_only_own_course(monkeypatch):
    at = _demo_login(_app(monkeypatch), "professor")
    assert [c["id"] for c in at.session_state["pdata"]["courses"]] == ["CSE311"]


# ---------------------------------------------------------------------------
# 역할 간 데이터 흐름: 학생 제출 → 교수 채점 → 학생 화면 반영
# ---------------------------------------------------------------------------
def test_submit_grade_roundtrip_across_roles(monkeypatch):
    at = _goto(_demo_login(_app(monkeypatch), "student"), "과제 제출")
    next(b for b in at.button if b.key == "submit-CSE311-A3").click().run()
    assert not at.exception

    # 교수로 로그인해 방금 제출된 과제를 채점한다.
    at = _click(at, "로그아웃")
    at = _goto(_demo_login(at, "professor"), "과제·채점")
    a3 = next(a for a in at.session_state["pdata"]["courses"][0]["assignments"] if a["id"] == "CSE311-A3")
    mine = next(s for s in a3["submissions"] if s["login_id"] == "202512345")
    assert mine["status"] == "submitted"
    at.number_input(key=f"score-{mine['id']}").set_value(21).run()
    next(b for b in at.button if b.key == f"grade-{mine['id']}").click().run()
    assert not at.exception

    # 다시 학생으로 들어오면 점수가 보인다.
    at = _click(at, "로그아웃")
    at = _demo_login(at, "student")
    a3 = next(a for a in at.session_state["courses"][0]["assignments"] if a["id"] == "CSE311-A3")
    assert (a3["status"], a3["score"]) == ("graded", 21)


def test_student_attendance_check_appends_week(monkeypatch):
    at = _goto(_demo_login(_app(monkeypatch), "student"), "출석 확인")
    before = len(at.session_state["attendance"]["CSE311"])
    next(b for b in at.button if b.key == "attend-CSE311").click().run()
    assert not at.exception
    assert len(at.session_state["attendance"]["CSE311"]) == before + 1


# ---------------------------------------------------------------------------
# DB 계층 권한 검사 (메모리 백엔드)
# ---------------------------------------------------------------------------
@pytest.fixture
def mem(monkeypatch):
    backend = db._MemoryBackend(sample.sample_tables())
    monkeypatch.setattr(db, "_backend", lambda: backend)
    return backend


def _user(login_id: str) -> dict:
    password = {"P": "prof1234"}.get(login_id[0], "student1234")
    user = db.login(login_id, password)
    assert user is not None
    return user


TODAY = date(2026, 4, 13)


def test_login_never_returns_password(mem):
    user = _user("P2001")
    assert "password" not in user and "password_hash" not in user


def test_login_rejects_bad_credentials(mem):
    assert db.login("P2001", "nope") is None
    assert db.login("", "x") is None
    assert db.login("nobody", "prof1234") is None


def test_other_professor_cannot_post_announcement(mem):
    with pytest.raises(db.PermissionDenied):
        db.post_announcement(_user("P2002"), "CSE311", "x", "y", False, TODAY)


def test_student_cannot_use_professor_actions(mem):
    with pytest.raises(db.PermissionDenied):
        db.post_announcement(_user("202512345"), "CSE311", "x", "y", False, TODAY)
    with pytest.raises(db.PermissionDenied):
        db.create_assignment(_user("202512345"), "CSE311", "x", TODAY, 10)


def test_student_cannot_submit_to_unenrolled_course(mem):
    with pytest.raises(db.PermissionDenied):
        db.submit_assignment(_user("202512346"), "GEN102-A2", TODAY)


def test_professor_cannot_submit_as_student(mem):
    with pytest.raises(db.PermissionDenied):
        db.submit_assignment(_user("P2001"), "CSE311-A3", TODAY)


def test_other_professor_cannot_grade(mem):
    with pytest.raises(db.PermissionDenied):
        db.grade_submission(_user("P2002"), 2, 10)


def test_grade_is_range_checked(mem):
    with pytest.raises(ValueError):
        db.grade_submission(_user("P2001"), 2, 999)  # CSE311-A2 는 30점 만점


def test_late_submission_is_flagged(mem):
    # CSE245-A2 마감(04-18)이 지난 04-20 에 제출하면 지각으로 기록된다.
    db.submit_assignment(_user("202512345"), "CSE245-A2", date(2026, 4, 20))
    sub = [s for s in mem.t["lms_submissions"]
           if s["assignment_id"] == "CSE245-A2" and s["student_id"] == _user("202512345")["id"]]
    assert len(sub) == 1 and sub[0]["late"] is True


def test_double_submit_does_not_duplicate(mem):
    me = _user("202512345")
    db.submit_assignment(me, "CSE311-A3", TODAY)
    db.submit_assignment(me, "CSE311-A3", TODAY)
    assert len([s for s in mem.t["lms_submissions"]
                if s["assignment_id"] == "CSE311-A3" and s["student_id"] == me["id"]]) == 1


def test_professor_answer_marks_question_answered(mem):
    db.answer_question(_user("P2002"), 2, "중복 키는 거부하세요.")
    q = next(q for q in db.load_student(_user("202512346"))["qna"] if q["id"] == 2)
    assert q["answered"] and q["replies"][0]["author"] == "이서연 교수"


def test_create_assignment_gets_next_id(mem):
    assert db.create_assignment(_user("P2001"), "CSE311", "신규", date(2026, 5, 1), 10) == "CSE311-A4"
