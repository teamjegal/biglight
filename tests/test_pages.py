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
ADMIN_PAGES = ["대시보드", "교수 관리", "강의 관리"]
STUDENT_BTN = "🎒 학생"
PROFESSOR_BTN = "🧑‍🏫 교수"
ADMIN_BTN = "🛠️ 관리자"


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
    label = {"student": STUDENT_BTN, "professor": PROFESSOR_BTN, "admin": ADMIN_BTN}[role]
    return _click(at, label)


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
    assert [t.label for t in at.text_input][:2] ==["학번", "비밀번호"]


def test_demo_buttons_are_shown_by_default(monkeypatch):
    monkeypatch.delenv("HIDE_DEMO_LOGINS", raising=False)
    at = _app(monkeypatch)
    assert {STUDENT_BTN, PROFESSOR_BTN, ADMIN_BTN} <= {b.label for b in at.button}


def test_demo_buttons_hidden_for_public_deploy(monkeypatch):
    monkeypatch.setenv("HIDE_DEMO_LOGINS", "1")
    at = _app(monkeypatch)
    labels = {b.label for b in at.button}
    assert not ({STUDENT_BTN, PROFESSOR_BTN, ADMIN_BTN} & labels)
    # 일반 로그인·회원가입은 그대로 동작한다.
    assert {"로그인", "회원가입"} <= labels
    assert "user" not in at.session_state


def test_professor_tab_asks_for_employee_id(monkeypatch):
    at = _app(monkeypatch)
    at.radio[0].set_value("교수").run()
    assert [t.label for t in at.text_input][:2] ==["사번", "비밀번호"]


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
    assert [t.label for t in at.text_input][:2] ==["학번", "비밀번호"]


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
    if login_id == "admin":
        password = "admin1234"
    else:
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


# ---------------------------------------------------------------------------
# 관리자: 로그인 탭, 화면, 교수 계정 생성
# ---------------------------------------------------------------------------
ADMIN_PW = sample.DEMO_LOGINS["admin"][1]


def _fill_new_professor(at: AppTest, login_id: str, name: str, password: str, admin_pw: str,
                        n: int = 0) -> AppTest:
    at.text_input(key=f"prof-id-{n}").set_value(login_id)
    at.text_input(key=f"prof-name-{n}").set_value(name)
    at.text_input(key=f"prof-dept-{n}").set_value("수학과")
    at.text_input(key=f"prof-pw-{n}").set_value(password)
    at.text_input(key=f"prof-admin-pw-{n}").set_value(admin_pw)
    return _click(at, "교수 계정 만들기")


def test_admin_tab_asks_for_admin_id(monkeypatch):
    at = _app(monkeypatch)
    at.radio[0].set_value("관리자").run()
    assert [t.label for t in at.text_input][:2] ==["관리자 ID", "비밀번호"]


def test_professor_cannot_login_on_admin_tab(monkeypatch):
    at = _form_login(_app(monkeypatch), "관리자", "P2001", "prof1234")
    assert "user" not in at.session_state
    assert any("관리자 계정이 아닙니다" in e.value for e in at.error)


@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_admin_page_renders(monkeypatch, page):
    at = _goto(_demo_login(_app(monkeypatch), "admin"), page)
    assert not at.exception, f"관리자 {page} 페이지 예외"


def test_admin_menu_is_separate_from_other_roles(monkeypatch):
    at = _demo_login(_app(monkeypatch), "admin")
    menu = {o.split(" ", 1)[1] for o in at.radio[0].options}
    assert menu == set(ADMIN_PAGES)


def test_admin_creates_professor_who_can_then_login(monkeypatch):
    at = _goto(_demo_login(_app(monkeypatch), "admin"), "교수 관리")
    at = _fill_new_professor(at, "P3001", "테스트교수", "newprof1234", ADMIN_PW)
    assert not at.error and not at.exception
    assert "P3001" in [p["login_id"] for p in at.session_state["adata"]["professors"]]

    # 새 교수로 로그인하면 담당 강의가 0개여도 모든 교수 화면이 깨지지 않는다.
    at = _click(at, "로그아웃")
    at = _form_login(at, "교수", "P3001", "newprof1234")
    assert at.session_state["user"]["name"] == "테스트교수"
    for page in PROFESSOR_PAGES:
        at = _goto(at, page)
        assert not at.exception, f"새 교수 {page} 페이지 예외"


def test_admin_wrong_password_does_not_create_professor(monkeypatch):
    at = _goto(_demo_login(_app(monkeypatch), "admin"), "교수 관리")
    at = _fill_new_professor(at, "P3002", "테스트교수", "newprof1234", "wrong-password")
    assert any("관리자 비밀번호가 올바르지 않습니다" in e.value for e in at.error)
    assert "P3002" not in [p["login_id"] for p in at.session_state["adata"]["professors"]]


# ---------------------------------------------------------------------------
# 관리자: DB 계층 (메모리 백엔드)
# ---------------------------------------------------------------------------
def test_new_courses_have_five_materials_each(mem):
    expected = {"MAT101": "P2004", "ECE201": "P2005", "CSE330": "P2006", "BUS110": "P2007", "ENG201": "P2008"}
    for course_id, prof in expected.items():
        view = db.load_professor(_user(prof))
        assert [c["id"] for c in view["courses"]] == [course_id]
        assert len(view["courses"][0]["materials"]) == 5


def test_load_admin_reports_totals(mem):
    stats = db.load_admin(_user("admin"))["stats"]
    assert stats == {"professors": 8, "students": 3, "courses": 8, "materials": 37}


def test_only_admin_can_use_admin_actions(mem):
    for who in ("P2001", "202512345"):
        user = _user(who)
        with pytest.raises(db.PermissionDenied):
            db.load_admin(user)
        with pytest.raises(db.PermissionDenied):
            db.create_professor(user, ADMIN_PW, "P9001", "longenough1", "x", "y")
        with pytest.raises(db.PermissionDenied):
            db.create_course(user, "ABC101", "x", 1, "", "")
        with pytest.raises(db.PermissionDenied):
            db.assign_professor(user, "CSE311", 2)


def test_create_professor_needs_correct_admin_password(mem):
    with pytest.raises(db.PermissionDenied):
        db.create_professor(_user("admin"), "wrong", "P9001", "longenough1", "이름", "학과")
    assert db.login("P9001", "longenough1") is None


def test_create_professor_validates_input(mem):
    admin = _user("admin")
    with pytest.raises(ValueError):  # 사번 중복
        db.create_professor(admin, ADMIN_PW, "P2001", "longenough1", "x", "y")
    with pytest.raises(ValueError):  # 짧은 비밀번호
        db.create_professor(admin, ADMIN_PW, "P9001", "short", "x", "y")
    with pytest.raises(ValueError):  # 사번 형식
        db.create_professor(admin, ADMIN_PW, "bad id!", "longenough1", "x", "y")
    with pytest.raises(ValueError):  # 이름 없음
        db.create_professor(admin, ADMIN_PW, "P9001", "longenough1", "  ", "y")


def test_created_account_is_always_professor_and_can_login(mem):
    db.create_professor(_user("admin"), ADMIN_PW, "P9001", "longenough1", "신규교수", "수학과")
    user = db.login("P9001", "longenough1")
    assert user["role"] == "professor" and user["name"] == "신규교수"


def test_create_course_then_professor_sees_it(mem):
    admin, prof = _user("admin"), _user("P2004")
    assert db.create_course(admin, "abc101", "신규 강의", prof["id"], "월 09:00", "101호") == "ABC101"
    assert [c["id"] for c in db.load_professor(prof)["courses"]] == ["MAT101", "ABC101"]


def test_create_course_validates_input(mem):
    admin = _user("admin")
    pid = _user("P2004")["id"]
    with pytest.raises(ValueError):  # 코드 형식
        db.create_course(admin, "1234", "x", pid, "", "")
    with pytest.raises(ValueError):  # 코드 중복
        db.create_course(admin, "CSE311", "x", pid, "", "")
    with pytest.raises(ValueError):  # 강의명 없음
        db.create_course(admin, "ABC101", " ", pid, "", "")
    with pytest.raises(ValueError):  # 담당자가 학생
        db.create_course(admin, "ABC101", "x", _user("202512345")["id"], "", "")


def test_assign_professor_moves_course(mem):
    admin, old, new = _user("admin"), _user("P2004"), _user("P2005")
    db.assign_professor(admin, "MAT101", new["id"])
    assert [c["id"] for c in db.load_professor(old)["courses"]] == []
    assert "MAT101" in [c["id"] for c in db.load_professor(new)["courses"]]


def test_assign_professor_rejects_non_professor_and_unknown_course(mem):
    admin = _user("admin")
    with pytest.raises(ValueError):
        db.assign_professor(admin, "MAT101", _user("202512345")["id"])
    with pytest.raises(ValueError):
        db.assign_professor(admin, "NOPE999", _user("P2004")["id"])


# ---------------------------------------------------------------------------
# 회원가입 (학생 전용)
# ---------------------------------------------------------------------------
def _fill_signup(at: AppTest, login_id: str, name: str, password: str, confirm: str | None = None,
                 department: str = "컴퓨터공학과") -> AppTest:
    at.text_input(key="su-id").set_value(login_id)
    at.text_input(key="su-name").set_value(name)
    at.text_input(key="su-dept").set_value(department)
    at.text_input(key="su-pw").set_value(password)
    at.text_input(key="su-pw2").set_value(password if confirm is None else confirm)
    return _click(at, "회원가입")


def test_signup_logs_in_new_student_with_empty_screens(monkeypatch):
    at = _fill_signup(_app(monkeypatch), "202699001", "신입생", "newstudent1")
    assert not at.exception and not at.error
    user = at.session_state["user"]
    assert (user["role"], user["name"], user["login_id"]) == ("student", "신입생", "202699001")
    assert at.session_state["courses"] == []
    # 수강 강의가 없어도 학생 화면 10개가 모두 깨지지 않는다.
    for page in STUDENT_PAGES:
        at = _goto(at, page)
        assert not at.exception, f"신규 학생 {page} 페이지 예외"


def test_signed_up_student_can_login_again(monkeypatch):
    at = _fill_signup(_app(monkeypatch), "202699002", "신입생", "newstudent1")
    at = _click(at, "로그아웃")
    at = _form_login(at, "학생", "202699002", "newstudent1")
    assert at.session_state["user"]["login_id"] == "202699002"


def test_signup_rejects_password_mismatch(monkeypatch):
    at = _fill_signup(_app(monkeypatch), "202699003", "신입생", "newstudent1", confirm="different1")
    assert "user" not in at.session_state
    assert any("서로 다릅니다" in e.value for e in at.error)


def test_signup_rejects_duplicate_student_id(monkeypatch):
    at = _fill_signup(_app(monkeypatch), "202512345", "다른사람", "newstudent1")
    assert "user" not in at.session_state
    assert any("이미 가입된 학번" in e.value for e in at.error)


def test_signup_rejects_bad_student_id_and_short_password(monkeypatch):
    at = _fill_signup(_app(monkeypatch), "abc123", "신입생", "newstudent1")
    assert "user" not in at.session_state and at.error
    at = _fill_signup(_app(monkeypatch), "202699004", "신입생", "short")
    assert "user" not in at.session_state and at.error


def test_signup_creates_only_student_accounts(mem):
    db.signup_student("202699005", "newstudent1", "신입생", "수학과")
    user = db.login("202699005", "newstudent1")
    assert user["role"] == "student" and user["department"] == "수학과"
    assert db.load_student(user)["courses"] == []


def test_signup_validates_input(mem):
    for args in [("12345", "newstudent1", "x", ""),        # 학번 5자리
                 ("2026990066", "short", "x", ""),          # 짧은 비밀번호 (학번은 유효)
                 ("202699007", "newstudent1", "  ", ""),     # 이름 없음
                 ("202512345", "newstudent1", "중복", "")]:  # 학번 중복
        with pytest.raises(ValueError):
            db.signup_student(*args)
