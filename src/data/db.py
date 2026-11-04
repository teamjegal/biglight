"""Supabase 백엔드 데이터 접근 계층 (로그인 + 학생/교수 역할).

앱은 이 모듈을 통해서만 데이터를 읽고 쓴다. 자격 증명(SUPABASE_URL/KEY)이
있으면 Supabase 를, 없으면 ``data.sample`` 의 가상 데이터를 담은 메모리 백엔드를
쓴다. 두 백엔드는 같은 인터페이스(select/insert/update/login)라서, 뷰를 만드는
로직과 쓰기 로직은 한 벌만 있다.

권한 모델: 역할(학생/교수) 검사는 이 모듈(앱 계층)에서 한다. DB 의 RLS 는 데모용
전체 허용이므로, 실서비스라면 Supabase Auth JWT 기반 RLS 로 DB 에서도 강제해야 한다.
비밀번호는 DB 에 해시로만 있고, 검증은 ``lms_login`` RPC 가 서버에서 한다.
"""

from __future__ import annotations

import copy
import os
import re
from collections import Counter
from datetime import date, datetime

import streamlit as st

from . import sample

# anon 키로는 password_hash 컬럼을 읽을 수 없으므로 사용자 조회는 이 컬럼만 쓴다.
USER_COLUMNS = "id,login_id,role,name,department,semester"


class PermissionDenied(Exception):
    """역할/소유권 검사에 걸린 쓰기 시도."""


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
    """Supabase 클라이언트(없으면 None). 서버 프로세스 동안 재사용."""
    url, key = _creds()
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception:
        return None


def is_connected() -> bool:
    """실제 Supabase 백엔드에 연결돼 있으면 True, 메모리(샘플) 모드면 False."""
    return _client() is not None


# ---------------------------------------------------------------------------
# 백엔드 — Supabase / 메모리. 인터페이스: select, insert, update, login.
# ---------------------------------------------------------------------------
def _jsonable(row: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in row.items()}


class _SupabaseBackend:
    def __init__(self, client):
        self.c = client

    def select(self, table: str, eq: dict | None = None, in_: dict | None = None) -> list[dict]:
        q = self.c.table(table).select(USER_COLUMNS if table == "lms_users" else "*")
        for k, v in (eq or {}).items():
            q = q.eq(k, v)
        for k, v in (in_ or {}).items():
            if not v:
                return []
            q = q.in_(k, list(v))
        return q.execute().data or []

    def insert(self, table: str, row: dict) -> dict:
        return self.c.table(table).insert(_jsonable(row)).execute().data[0]

    def update(self, table: str, values: dict, eq: dict) -> None:
        q = self.c.table(table).update(_jsonable(values))
        for k, v in eq.items():
            q = q.eq(k, v)
        q.execute()

    def login(self, login_id: str, password: str) -> dict | None:
        data = self.c.rpc("lms_login", {"p_login_id": login_id, "p_password": password}).execute().data
        return data[0] if data else None

    def create_user(self, admin_login_id: str, admin_password: str, row: dict) -> int:
        """교수 계정 생성. 관리자 자격은 DB 함수가 호출마다 다시 검증한다."""
        try:
            res = self.c.rpc("lms_admin_create_user", {
                "p_admin_id": admin_login_id, "p_admin_password": admin_password,
                "p_login_id": row["login_id"], "p_password": row["password"],
                "p_name": row["name"], "p_department": row.get("department") or "",
                "p_semester": row.get("semester") or "",
            }).execute()
        except Exception as exc:  # postgrest APIError — SQLSTATE 로 원인을 구분한다.
            code = getattr(exc, "code", None)
            if code == "42501":
                raise PermissionDenied("관리자 비밀번호가 올바르지 않습니다.") from exc
            if code == "23505":
                raise ValueError("이미 사용 중인 사번입니다.") from exc
            if code == "22023":
                raise ValueError("입력값이 올바르지 않습니다.") from exc
            raise
        return res.data


class _MemoryBackend:
    """샘플 데이터를 세션 상태에 두고 같은 인터페이스로 읽고 쓴다."""

    def __init__(self, tables: dict[str, list[dict]]):
        self.t = tables

    @staticmethod
    def _public(table: str, row: dict) -> dict:
        row = copy.deepcopy(row)
        if table == "lms_users":
            row.pop("password", None)
        return row

    def select(self, table: str, eq: dict | None = None, in_: dict | None = None) -> list[dict]:
        out = []
        for r in self.t[table]:
            if any(r.get(k) != v for k, v in (eq or {}).items()):
                continue
            if any(r.get(k) not in set(v) for k, v in (in_ or {}).items()):
                continue
            out.append(self._public(table, r))
        return out

    def insert(self, table: str, row: dict) -> dict:
        rows = self.t[table]
        new = dict(row)
        if "id" not in new:
            new["id"] = max((r["id"] for r in rows if isinstance(r.get("id"), int)), default=0) + 1
        rows.append(new)
        return self._public(table, new)

    def update(self, table: str, values: dict, eq: dict) -> None:
        for r in self.t[table]:
            if all(r.get(k) == v for k, v in eq.items()):
                r.update(values)

    def login(self, login_id: str, password: str) -> dict | None:
        for u in self.t["lms_users"]:
            if u["login_id"] == login_id and u["password"] == password:
                return self._public("lms_users", u)
        return None

    def create_user(self, admin_login_id: str, admin_password: str, row: dict) -> int:
        """Supabase 의 lms_admin_create_user 와 같은 규칙(샘플 모드용)."""
        users = self.t["lms_users"]
        if not any(u["login_id"] == admin_login_id and u["role"] == "admin"
                   and u["password"] == admin_password for u in users):
            raise PermissionDenied("관리자 비밀번호가 올바르지 않습니다.")
        login_id, name = row["login_id"].strip(), row["name"].strip()
        if len(row["password"]) < 8 or not login_id or not name:
            raise ValueError("입력값이 올바르지 않습니다.")
        if any(u["login_id"] == login_id for u in users):
            raise ValueError("이미 사용 중인 사번입니다.")
        return self.insert("lms_users", {
            "login_id": login_id, "password": row["password"], "role": "professor", "name": name,
            "department": (row.get("department") or "").strip() or None,
            "semester": row.get("semester") or None})["id"]


def _backend():
    client = _client()
    if client is not None:
        return _SupabaseBackend(client)
    if "_mem_tables" not in st.session_state:
        st.session_state["_mem_tables"] = sample.sample_tables()
    return _MemoryBackend(st.session_state["_mem_tables"])


def _to_date(value):
    """DB 가 돌려준 날짜 문자열(또는 date/datetime)을 ``date`` 로 변환."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _session_user(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "login_id", "role", "name", "department", "semester")}


# ---------------------------------------------------------------------------
# 로그인
# ---------------------------------------------------------------------------
def login(login_id: str, password: str) -> dict | None:
    """아이디/비밀번호가 맞으면 사용자 dict, 아니면 None. 연결 오류는 예외."""
    login_id = (login_id or "").strip()
    if not login_id or not password:
        return None
    row = _backend().login(login_id, password)
    return _session_user(row) if row else None


# ---------------------------------------------------------------------------
# 읽기 — 학생 뷰
# ---------------------------------------------------------------------------
def _course_meta(courses_raw: list[dict]) -> tuple[dict, dict]:
    colors = {c["id"]: c.get("card_color") or "#3b5bdb" for c in courses_raw}
    codes = {c["id"]: c.get("course_code") or c["id"] for c in courses_raw}
    return colors, codes


def _material(m: dict) -> dict:
    return {"id": m["id"], "week": m["week"], "title": m["title"], "type": m["type"],
            "size_kb": m["size_kb"], "posted": _to_date(m["posted"])}


def _announcement(a: dict) -> dict:
    return {"id": a["id"], "course_id": a["course_id"], "title": a["title"], "body": a["body"],
            "posted": _to_date(a["posted"]), "pinned": bool(a["pinned"])}


def _qna_posts(b, course_ids: list[str]) -> list[dict]:
    posts = b.select("lms_qna", in_={"course_id": course_ids})
    replies: dict[int, list] = {}
    for r in sorted(b.select("lms_qna_replies", in_={"qna_id": [q["id"] for q in posts]}),
                    key=lambda r: r["id"]):
        replies.setdefault(r["qna_id"], []).append({"author": r["author"], "body": r["body"]})
    return [
        {"id": q["id"], "course_id": q["course_id"], "author": q["author"], "title": q["title"],
         "body": q["body"], "posted": _to_date(q["posted"]), "answered": bool(q["answered"]),
         "replies": replies.get(q["id"], [])}
        for q in sorted(posts, key=lambda q: q["id"])
    ]


def load_student(user: dict) -> dict:
    """로그인한 학생의 화면용 데이터 한 벌."""
    b = _backend()
    sid = user["id"]
    cids = [e["course_id"] for e in b.select("lms_enrollments", eq={"student_id": sid})]
    courses_raw = sorted(b.select("lms_courses", in_={"id": cids}), key=lambda c: c.get("sort_order") or 0)
    cids = [c["id"] for c in courses_raw]
    profs = {u["id"]: u["name"] for u in
             b.select("lms_users", in_={"id": [c["professor_id"] for c in courses_raw if c.get("professor_id")]})}

    mats: dict[str, list] = {}
    for m in b.select("lms_materials", in_={"course_id": cids}):
        mats.setdefault(m["course_id"], []).append(_material(m))
    subs = {s["assignment_id"]: s for s in b.select("lms_submissions", eq={"student_id": sid})}
    asg: dict[str, list] = {}
    for a in sorted(b.select("lms_assignments", in_={"course_id": cids}), key=lambda a: a["id"]):
        s = subs.get(a["id"])
        asg.setdefault(a["course_id"], []).append({
            "id": a["id"], "title": a["title"], "due": _to_date(a["due"]), "points": a["points"],
            "status": s["status"] if s else "open",
            "score": s["score"] if s else None,
            "late": bool(s and s.get("late")),
        })

    courses = [{
        "id": c["id"], "title": c["title"], "professor": profs.get(c.get("professor_id"), ""),
        "schedule": c["schedule"], "room": c["room"],
        "materials": sorted(mats.get(c["id"], []), key=lambda m: m["week"]),
        "assignments": asg.get(c["id"], []),
    } for c in courses_raw]

    attendance: dict[str, list] = {cid: [] for cid in cids}
    for r in sorted(b.select("lms_attendance", eq={"student_id": sid}), key=lambda r: r["week"]):
        if r["course_id"] in attendance:
            attendance[r["course_id"]].append(
                {"week": r["week"], "date": _to_date(r["date"]), "status": r["status"]})

    lectures: dict[str, list] = {cid: [] for cid in cids}
    progress = {p["lecture_id"]: p["watched_pct"] for p in b.select("lms_lecture_progress", eq={"student_id": sid})}
    for v in sorted(b.select("lms_lectures", in_={"course_id": cids}), key=lambda v: (v["course_id"], v["week"])):
        lectures[v["course_id"]].append({
            "id": v["id"], "week": v["week"], "title": v["title"],
            "duration_min": v["duration_min"], "watched_pct": progress.get(v["id"], 0)})

    exams: dict[str, list] = {cid: [] for cid in cids}
    for e in b.select("lms_exams", eq={"student_id": sid}):
        if e["course_id"] in exams:
            exams[e["course_id"]].append(
                {"name": e["name"], "score": e["score"], "max": e["max"], "date": _to_date(e["date"])})

    announcements = [_announcement(a) for a in b.select("lms_announcements")
                     if a["course_id"] is None or a["course_id"] in cids]
    colors, codes = _course_meta(courses_raw)
    return {
        "user": user,
        "student": {"name": user["name"], "student_id": user["login_id"],
                    "major": user["department"], "semester": user["semester"]},
        "courses": courses, "attendance": attendance, "lectures": lectures, "exams": exams,
        "announcements": announcements, "qna": _qna_posts(b, cids),
        "card_colors": colors, "course_code": codes,
    }


# ---------------------------------------------------------------------------
# 읽기 — 교수 뷰
# ---------------------------------------------------------------------------
def load_professor(user: dict) -> dict:
    """로그인한 교수가 맡은 과목들의 관리 화면용 데이터 한 벌."""
    b = _backend()
    courses_raw = sorted(b.select("lms_courses", eq={"professor_id": user["id"]}),
                         key=lambda c: c.get("sort_order") or 0)
    cids = [c["id"] for c in courses_raw]

    enroll = b.select("lms_enrollments", in_={"course_id": cids})
    students = {u["id"]: u for u in b.select("lms_users", in_={"id": sorted({e["student_id"] for e in enroll})})}
    roster: dict[str, list] = {cid: [] for cid in cids}
    for e in enroll:
        u = students.get(e["student_id"])
        if u:
            roster[e["course_id"]].append({"id": u["id"], "name": u["name"], "login_id": u["login_id"]})
    for rows in roster.values():
        rows.sort(key=lambda s: s["login_id"])

    mats: dict[str, list] = {cid: [] for cid in cids}
    for m in b.select("lms_materials", in_={"course_id": cids}):
        mats[m["course_id"]].append(_material(m))

    asg_raw = sorted(b.select("lms_assignments", in_={"course_id": cids}), key=lambda a: a["id"])
    subs_by: dict[str, list] = {}
    for s in sorted(b.select("lms_submissions", in_={"assignment_id": [a["id"] for a in asg_raw]}),
                    key=lambda s: s["id"]):
        stu = students.get(s["student_id"], {})
        subs_by.setdefault(s["assignment_id"], []).append({
            "id": s["id"], "student_id": s["student_id"], "student_name": stu.get("name", "?"),
            "login_id": stu.get("login_id", ""), "status": s["status"], "score": s["score"],
            "late": bool(s.get("late")), "submitted_at": _to_date(s["submitted_at"])})
    asg: dict[str, list] = {cid: [] for cid in cids}
    for a in asg_raw:
        submissions = subs_by.get(a["id"], [])
        done = {s["student_id"] for s in submissions}
        asg[a["course_id"]].append({
            "id": a["id"], "title": a["title"], "due": _to_date(a["due"]), "points": a["points"],
            "submissions": submissions,
            "missing": [s for s in roster[a["course_id"]] if s["id"] not in done]})

    attendance: dict[str, dict] = {cid: {} for cid in cids}
    for r in b.select("lms_attendance", in_={"course_id": cids}):
        attendance[r["course_id"]].setdefault(r["student_id"], {})[r["week"]] = r["status"]

    courses = [{
        "id": c["id"], "title": c["title"], "professor": user["name"], "schedule": c["schedule"],
        "room": c["room"], "roster": roster[c["id"]],
        "materials": sorted(mats[c["id"]], key=lambda m: m["week"]),
        "assignments": asg[c["id"]],
    } for c in courses_raw]

    announcements = [_announcement(a) for a in b.select("lms_announcements", in_={"course_id": cids})]
    colors, codes = _course_meta(courses_raw)
    return {
        "user": user,
        "professor": {"name": user["name"], "login_id": user["login_id"],
                      "department": user["department"], "semester": user["semester"]},
        "courses": courses, "attendance": attendance, "announcements": announcements,
        "qna": _qna_posts(b, cids), "card_colors": colors, "course_code": codes,
    }


# ---------------------------------------------------------------------------
# 쓰기 — 공통 권한 검사
# ---------------------------------------------------------------------------
def _require(user: dict, role: str) -> None:
    if not user or user.get("role") != role:
        raise PermissionDenied(f"{role} 권한이 필요합니다.")


def _own_course(b, user: dict, course_id: str) -> dict:
    """교수가 담당하는 과목인지 확인하고 과목 행을 돌려준다."""
    _require(user, "professor")
    rows = b.select("lms_courses", eq={"id": course_id})
    if not rows or rows[0].get("professor_id") != user["id"]:
        raise PermissionDenied("담당 과목이 아닙니다.")
    return rows[0]


def _enrolled(b, user: dict, course_id: str) -> None:
    _require(user, "student")
    if not b.select("lms_enrollments", eq={"course_id": course_id, "student_id": user["id"]}):
        raise PermissionDenied("수강 중인 과목이 아닙니다.")


# ---------------------------------------------------------------------------
# 쓰기 — 학생
# ---------------------------------------------------------------------------
def submit_assignment(user: dict, assignment_id: str, on_date: date) -> None:
    b = _backend()
    rows = b.select("lms_assignments", eq={"id": assignment_id})
    if not rows:
        raise ValueError("존재하지 않는 과제입니다.")
    asg = rows[0]
    _enrolled(b, user, asg["course_id"])
    existing = b.select("lms_submissions", eq={"assignment_id": assignment_id, "student_id": user["id"]})
    if existing:  # 이미 제출했으면 중복 생성하지 않는다(채점된 건 되돌리지 않음).
        return
    b.insert("lms_submissions", {
        "assignment_id": assignment_id, "student_id": user["id"], "status": "submitted",
        "score": None, "late": on_date > _to_date(asg["due"]), "submitted_at": on_date})


def check_attendance(user: dict, course_id: str, week: int, on_date: date, status: str = "present") -> None:
    b = _backend()
    _enrolled(b, user, course_id)
    _upsert_attendance(b, course_id, user["id"], week, on_date, status)


def watch_lecture(user: dict, lecture_id: int) -> None:
    b = _backend()
    lec = b.select("lms_lectures", eq={"id": lecture_id})
    if not lec:
        raise ValueError("존재하지 않는 강의입니다.")
    _enrolled(b, user, lec[0]["course_id"])
    cur = b.select("lms_lecture_progress", eq={"lecture_id": lecture_id, "student_id": user["id"]})
    if cur:
        b.update("lms_lecture_progress", {"watched_pct": 100}, {"id": cur[0]["id"]})
    else:
        b.insert("lms_lecture_progress", {"lecture_id": lecture_id, "student_id": user["id"], "watched_pct": 100})


def add_question(user: dict, course_id: str, title: str, body: str, on_date: date) -> None:
    b = _backend()
    _enrolled(b, user, course_id)
    b.insert("lms_qna", {"course_id": course_id, "author_id": user["id"], "author": user["name"],
                         "title": title, "body": body, "posted": on_date, "answered": False})


# ---------------------------------------------------------------------------
# 쓰기 — 교수
# ---------------------------------------------------------------------------
def _upsert_attendance(b, course_id: str, student_id: int, week: int, on_date: date, status: str) -> None:
    if status not in ("present", "late", "absent"):
        raise ValueError("잘못된 출석 상태입니다.")
    cur = b.select("lms_attendance", eq={"course_id": course_id, "student_id": student_id, "week": week})
    if cur:
        b.update("lms_attendance", {"status": status}, {"id": cur[0]["id"]})
    else:
        b.insert("lms_attendance", {"course_id": course_id, "student_id": student_id, "week": week,
                                    "date": on_date, "status": status})


def set_attendance(user: dict, course_id: str, student_id: int, week: int, on_date: date, status: str) -> None:
    b = _backend()
    _own_course(b, user, course_id)
    if not b.select("lms_enrollments", eq={"course_id": course_id, "student_id": student_id}):
        raise PermissionDenied("수강생이 아닙니다.")
    _upsert_attendance(b, course_id, student_id, week, on_date, status)


def post_announcement(user: dict, course_id: str, title: str, body: str, pinned: bool, on_date: date) -> None:
    b = _backend()
    _own_course(b, user, course_id)
    b.insert("lms_announcements", {"course_id": course_id, "author_id": user["id"], "title": title,
                                   "body": body, "posted": on_date, "pinned": pinned})


def add_material(user: dict, course_id: str, week: int, title: str, kind: str, size_kb: int, on_date: date) -> None:
    b = _backend()
    _own_course(b, user, course_id)
    b.insert("lms_materials", {"course_id": course_id, "week": week, "title": title, "type": kind,
                               "size_kb": size_kb, "posted": on_date})


def create_assignment(user: dict, course_id: str, title: str, due: date, points: int) -> str:
    b = _backend()
    _own_course(b, user, course_id)
    nums = []
    for a in b.select("lms_assignments", eq={"course_id": course_id}):
        tail = a["id"].rsplit("-A", 1)[-1]
        if tail.isdigit():
            nums.append(int(tail))
    new_id = f"{course_id}-A{max(nums, default=0) + 1}"
    b.insert("lms_assignments", {"id": new_id, "course_id": course_id, "title": title,
                                 "due": due, "points": points})
    return new_id


def grade_submission(user: dict, submission_id: int, score: int) -> None:
    b = _backend()
    sub = b.select("lms_submissions", eq={"id": submission_id})
    if not sub:
        raise ValueError("존재하지 않는 제출물입니다.")
    asg = b.select("lms_assignments", eq={"id": sub[0]["assignment_id"]})[0]
    _own_course(b, user, asg["course_id"])
    if not 0 <= score <= asg["points"]:
        raise ValueError(f"점수는 0~{asg['points']} 사이여야 합니다.")
    b.update("lms_submissions", {"status": "graded", "score": score}, {"id": submission_id})


def answer_question(user: dict, qna_id: int, body: str) -> None:
    b = _backend()
    q = b.select("lms_qna", eq={"id": qna_id})
    if not q:
        raise ValueError("존재하지 않는 질문입니다.")
    _own_course(b, user, q[0]["course_id"])
    b.insert("lms_qna_replies", {"qna_id": qna_id, "author_id": user["id"],
                                 "author": f"{user['name']} 교수", "body": body})
    b.update("lms_qna", {"answered": True}, {"id": qna_id})


# ---------------------------------------------------------------------------
# 관리자
# ---------------------------------------------------------------------------
COURSE_PALETTE = ["#3b5bdb", "#2f9e44", "#e8590c", "#7048e8", "#0c8599", "#c2255c", "#5c940d", "#e67700"]
LOGIN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
COURSE_ID_RE = re.compile(r"^[A-Z]{2,4}\d{3}$")
MIN_PASSWORD = 8


def load_admin(user: dict) -> dict:
    """관리자 화면용 데이터: 전체 교수·강의 현황."""
    _require(user, "admin")
    b = _backend()
    users = b.select("lms_users")
    professors = sorted((u for u in users if u["role"] == "professor"), key=lambda u: u["login_id"])
    n_students = sum(1 for u in users if u["role"] == "student")
    courses_raw = sorted(b.select("lms_courses"), key=lambda c: c.get("sort_order") or 0)
    enrolled = Counter(e["course_id"] for e in b.select("lms_enrollments"))
    materials = Counter(m["course_id"] for m in b.select("lms_materials"))
    teaching = Counter(c["professor_id"] for c in courses_raw)
    names = {u["id"]: u["name"] for u in professors}
    return {
        "user": user,
        "admin": {"name": user["name"], "login_id": user["login_id"],
                  "department": user["department"], "semester": user["semester"]},
        "professors": [{"id": u["id"], "login_id": u["login_id"], "name": u["name"],
                        "department": u["department"], "courses": teaching.get(u["id"], 0)}
                       for u in professors],
        "courses": [{"id": c["id"], "title": c["title"], "professor_id": c["professor_id"],
                     "professor": names.get(c["professor_id"], "(미배정)"), "schedule": c["schedule"],
                     "room": c["room"], "students": enrolled.get(c["id"], 0),
                     "materials": materials.get(c["id"], 0)} for c in courses_raw],
        "stats": {"professors": len(professors), "students": n_students,
                  "courses": len(courses_raw), "materials": sum(materials.values())},
    }


def _professor_row(b, professor_id: int) -> dict:
    rows = b.select("lms_users", eq={"id": professor_id})
    if not rows or rows[0]["role"] != "professor":
        raise ValueError("교수 계정을 선택하세요.")
    return rows[0]


def create_professor(user: dict, admin_password: str, login_id: str, password: str,
                     name: str, department: str) -> int:
    """교수 계정을 만든다. 관리자 비밀번호를 서버가 다시 검증한다."""
    _require(user, "admin")
    login_id, name = (login_id or "").strip(), (name or "").strip()
    if not LOGIN_ID_RE.match(login_id):
        raise ValueError("사번은 영문·숫자·-·_ 3~20자로 입력하세요.")
    if not name:
        raise ValueError("이름을 입력하세요.")
    if len(password or "") < MIN_PASSWORD:
        raise ValueError(f"비밀번호는 {MIN_PASSWORD}자 이상이어야 합니다.")
    if not admin_password:
        raise ValueError("관리자 비밀번호를 입력하세요.")
    return _backend().create_user(
        user["login_id"], admin_password,
        {"login_id": login_id, "password": password, "name": name,
         "department": (department or "").strip(), "semester": user.get("semester")})


def create_course(user: dict, course_id: str, title: str, professor_id: int,
                  schedule: str, room: str) -> str:
    """새 강의를 열고 담당 교수를 배정한다."""
    _require(user, "admin")
    b = _backend()
    course_id, title = (course_id or "").strip().upper(), (title or "").strip()
    if not COURSE_ID_RE.match(course_id):
        raise ValueError("강의 코드는 영문 대문자 2~4자 + 숫자 3자리(예: CSE101)로 입력하세요.")
    if not title:
        raise ValueError("강의명을 입력하세요.")
    _professor_row(b, professor_id)
    existing = b.select("lms_courses")
    if any(c["id"] == course_id for c in existing):
        raise ValueError("이미 있는 강의 코드입니다.")
    n = len(existing)
    b.insert("lms_courses", {
        "id": course_id, "title": title, "professor_id": professor_id,
        "schedule": (schedule or "").strip() or None, "room": (room or "").strip() or None,
        "card_color": COURSE_PALETTE[n % len(COURSE_PALETTE)], "course_code": f"9{n + 1:09d}",
        "sort_order": max((c.get("sort_order") or 0 for c in existing), default=0) + 1})
    return course_id


def assign_professor(user: dict, course_id: str, professor_id: int) -> None:
    """강의의 담당 교수를 바꾼다."""
    _require(user, "admin")
    b = _backend()
    if not b.select("lms_courses", eq={"id": course_id}):
        raise ValueError("존재하지 않는 강의입니다.")
    _professor_row(b, professor_id)
    b.update("lms_courses", {"professor_id": professor_id}, {"id": course_id})
