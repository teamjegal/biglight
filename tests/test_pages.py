"""클래스허브 LMS 페이지 렌더링·상호작용 스모크 테스트.

CI/오프라인에서도 돌도록 네트워크를 쓰지 않는다. ``data.db._client`` 를
None 으로 패치해 항상 샘플 폴백 모드로 실행하므로, 실제 Supabase 연결 없이도
전 페이지가 예외 없이 그려지는지와 기본 상호작용을 검증할 수 있다.
"""

from __future__ import annotations

from pathlib import Path

import data.db as db
import pytest
from streamlit.testing.v1 import AppTest

# 프로젝트 루트/src/main.py — AppTest 는 상대 경로를 호출 파일 기준으로 풀기에
# 절대 경로로 지정한다.
APP = str(Path(__file__).resolve().parents[1] / "src" / "main.py")

PAGES = [
    "수강 강좌",
    "대시보드",
    "공지사항",
    "강의 자료",
    "온라인 강의",
    "과제 제출",
    "출석 확인",
    "성적 조회",
    "시간표",
    "Q&A 게시판",
]


def _run(monkeypatch, page: str | None = None) -> AppTest:
    """샘플 폴백 모드로 앱을 실행하고, 필요하면 특정 페이지로 이동한다."""
    monkeypatch.setattr(db, "_client", lambda: None)
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    if page is not None:
        opt = next(o for o in at.radio[0].options if o.endswith(page))
        at.radio[0].set_value(opt).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(monkeypatch, page):
    at = _run(monkeypatch, page)
    assert not at.exception, f"{page} 페이지에서 예외 발생"


def test_runs_in_fallback_mode_without_network(monkeypatch):
    at = _run(monkeypatch)
    assert at.session_state["connected"] is False
    # 샘플 데이터가 로드됐는지(과목 3개).
    assert len(at.session_state["courses"]) == 3


def test_submit_assignment_marks_submitted(monkeypatch):
    at = _run(monkeypatch, "과제 제출")
    button = next(b for b in at.button if b.key == "submit-CSE311-A3")
    button.click().run()
    assert not at.exception
    assignment = next(
        a
        for c in at.session_state["courses"]
        if c["id"] == "CSE311"
        for a in c["assignments"]
        if a["id"] == "CSE311-A3"
    )
    assert assignment["status"] == "submitted"


def test_check_attendance_appends_week(monkeypatch):
    at = _run(monkeypatch, "출석 확인")
    before = len(at.session_state["attendance"]["CSE311"])
    next(b for b in at.button if b.key == "attend-CSE311").click().run()
    assert not at.exception
    assert len(at.session_state["attendance"]["CSE311"]) == before + 1
