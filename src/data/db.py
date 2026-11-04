"""Supabase 백엔드 데이터 접근 계층.

앱은 이 모듈을 통해서만 데이터를 읽고 쓴다. 자격 증명(SUPABASE_URL/KEY)이
설정돼 있으면 Supabase와 통신하고, 없거나 통신에 실패하면 ``data.sample``의
가상 데이터로 자동 폴백한다. 덕분에 테스트·오프라인 환경에서도 앱이 그대로
동작한다.

반환 구조는 기존 ``data.sample``과 동일한 모양(날짜는 ``datetime.date``)이라
페이지 코드를 거의 바꾸지 않고 연동할 수 있다.
"""

from __future__ import annotations

import copy
import os
from datetime import date, datetime

import streamlit as st

from . import sample


# ---------------------------------------------------------------------------
# 연결
# ---------------------------------------------------------------------------
def _creds() -> tuple[str | None, str | None]:
    """환경 변수 → Streamlit secrets 순으로 자격 증명을 찾는다."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not (url and key):
        try:  # secrets.toml 이 없으면 접근 자체가 예외를 던질 수 있다.
            url = url or st.secrets["SUPABASE_URL"]
            key = key or st.secrets["SUPABASE_KEY"]
        except Exception:
            pass
    return url, key


@st.cache_resource(show_spinner=False)
def _client():
    """Supabase 클라이언트(없으면 None). 세션 동안 재사용."""
    url, key = _creds()
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception:
        return None


def is_connected() -> bool:
    """실제 Supabase 백엔드에 연결돼 있으면 True, 폴백 모드면 False."""
    return _client() is not None


def _to_date(value):
    """DB가 돌려준 날짜/타임스탬프 문자열을 ``date`` 로 변환."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


# ---------------------------------------------------------------------------
# 읽기
# ---------------------------------------------------------------------------
def _rows(client, table: str, order: str | None = None):
    q = client.table(table).select("*")
    if order:
        q = q.order(order)
    return q.execute().data or []


def _load_from_db(client) -> dict:
    # 과목 + 자료 + 과제를 한 번에 읽어 과목 단위로 묶는다.
    course_rows = _rows(client, "lms_courses", "sort_order")
    mat_rows = _rows(client, "lms_materials", "week")
    asg_rows = _rows(client, "lms_assignments", "id")

    mats_by: dict[str, list] = {}
    for m in mat_rows:
        mats_by.setdefault(m["course_id"], []).append(
            {
                "week": m["week"],
                "title": m["title"],
                "type": m["type"],
                "size_kb": m["size_kb"],
                "posted": _to_date(m["posted"]),
            }
        )

    asg_by: dict[str, list] = {}
    for a in asg_rows:
        asg_by.setdefault(a["course_id"], []).append(
            {
                "id": a["id"],
                "title": a["title"],
                "due": _to_date(a["due"]),
                "points": a["points"],
                "status": a["status"],
                "score": a["score"],
            }
        )

    courses, card_colors, course_code = [], {}, {}
    for c in course_rows:
        courses.append(
            {
                "id": c["id"],
                "title": c["title"],
                "professor": c["professor"],
                "schedule": c["schedule"],
                "room": c["room"],
                "materials": mats_by.get(c["id"], []),
                "assignments": asg_by.get(c["id"], []),
            }
        )
        card_colors[c["id"]] = c.get("card_color") or "#3b5bdb"
        course_code[c["id"]] = c.get("course_code") or c["id"]

    attendance: dict[str, list] = {}
    for r in _rows(client, "lms_attendance", "week"):
        attendance.setdefault(r["course_id"], []).append(
            {"week": r["week"], "date": _to_date(r["date"]), "status": r["status"]}
        )

    announcements = [
        {
            "course_id": a["course_id"],
            "title": a["title"],
            "body": a["body"],
            "posted": _to_date(a["posted"]),
            "pinned": a["pinned"],
        }
        for a in _rows(client, "lms_announcements")
    ]

    exams: dict[str, list] = {c["id"]: [] for c in course_rows}
    for e in _rows(client, "lms_exams"):
        exams.setdefault(e["course_id"], []).append(
            {"name": e["name"], "score": e["score"], "max": e["max"], "date": _to_date(e["date"])}
        )

    lectures: dict[str, list] = {}
    for v in _rows(client, "lms_lectures", "week"):
        lectures.setdefault(v["course_id"], []).append(
            {
                "id": v["id"],
                "week": v["week"],
                "title": v["title"],
                "duration_min": v["duration_min"],
                "watched_pct": v["watched_pct"],
            }
        )

    reps_by: dict[int, list] = {}
    for r in _rows(client, "lms_qna_replies", "created_at"):
        reps_by.setdefault(r["qna_id"], []).append({"author": r["author"], "body": r["body"]})
    qna = [
        {
            "id": q["id"],
            "course_id": q["course_id"],
            "author": q["author"],
            "title": q["title"],
            "body": q["body"],
            "posted": _to_date(q["posted"]),
            "answered": q["answered"],
            "replies": reps_by.get(q["id"], []),
        }
        for q in _rows(client, "lms_qna", "posted")
    ]

    student_rows = _rows(client, "lms_students")
    if student_rows:
        s = student_rows[0]
        student = {
            "name": s["name"],
            "student_id": s["student_id"],
            "major": s["major"],
            "semester": s["semester"],
        }
    else:
        student = copy.deepcopy(sample.DEMO_STUDENT)

    return {
        "courses": courses,
        "attendance": attendance,
        "qna": qna,
        "lectures": lectures,
        "announcements": announcements,
        "exams": exams,
        "student": student,
        "card_colors": card_colors,
        "course_code": course_code,
    }


def _load_from_sample() -> dict:
    return {
        "courses": copy.deepcopy(sample.COURSES),
        "attendance": copy.deepcopy(sample.ATTENDANCE),
        "qna": copy.deepcopy(sample.QNA),
        "lectures": copy.deepcopy(sample.LECTURES),
        "announcements": copy.deepcopy(sample.ANNOUNCEMENTS),
        "exams": copy.deepcopy(sample.EXAMS),
        "student": copy.deepcopy(sample.DEMO_STUDENT),
        "card_colors": copy.deepcopy(sample.CARD_COLORS),
        "course_code": copy.deepcopy(sample.COURSE_CODE),
    }


def load_all() -> dict:
    """앱이 쓰는 모든 데이터를 한 번에 로드. 실패 시 샘플로 폴백."""
    client = _client()
    if client is None:
        return _load_from_sample()
    try:
        return _load_from_db(client)
    except Exception as exc:  # 네트워크/권한 문제 등 — 데모가 멈추지 않게 폴백.
        st.session_state["_db_error"] = str(exc)
        return _load_from_sample()


# ---------------------------------------------------------------------------
# 쓰기 — 연결돼 있을 때만 수행(폴백 모드에서는 호출부가 세션을 직접 수정).
# ---------------------------------------------------------------------------
def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def submit_assignment(assignment_id: str) -> bool:
    client = _client()
    if client is None:
        return False
    client.table("lms_assignments").update({"status": "submitted"}).eq(
        "id", assignment_id
    ).execute()
    return True


def check_attendance(course_id: str, week: int, on_date, status: str = "present") -> bool:
    client = _client()
    if client is None:
        return False
    client.table("lms_attendance").insert(
        {"course_id": course_id, "week": week, "date": _iso(on_date), "status": status}
    ).execute()
    return True


def watch_lecture(lecture_id: int) -> bool:
    client = _client()
    if client is None:
        return False
    client.table("lms_lectures").update({"watched_pct": 100}).eq("id", lecture_id).execute()
    return True


def add_question(course_id: str, title: str, body: str, on_date) -> bool:
    client = _client()
    if client is None:
        return False
    client.table("lms_qna").insert(
        {
            "course_id": course_id,
            "author": "학생",
            "title": title,
            "body": body,
            "posted": _iso(on_date),
            "answered": False,
        }
    ).execute()
    return True
