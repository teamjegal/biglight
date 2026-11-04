"""데모용 샘플 데이터.

실제 서비스가 아니라 화면을 채우기 위한 가짜 데이터다. 모든 이름과 과목은
가상의 것이며 특정 학교나 기관과 관련이 없다.

Supabase 에 연결되지 않았을 때(테스트·오프라인) 쓰는 폴백이며, DB 스키마
(supabase/migrations)와 같은 관계형 구조(``sample_tables()``)로 돼 있다.
supabase/seed.sql 과 내용을 맞춰 둔다.
"""

from __future__ import annotations

from datetime import date

# 데모를 여는 '오늘'을 고정해 화면이 항상 같은 상태로 보이게 한다.
TODAY = date(2026, 4, 13)

SEMESTER = "2026학년도 1학기"

# 폴백 모드 로그인과 '데모 계정으로 시작' 버튼에 쓰는 공개 데모 계정.
# (supabase/seed.sql 과 동일. 실서비스 계정에 같은 값을 쓰지 말 것.)
DEMO_LOGINS = {
    "student": ("202512345", "student1234"),
    "professor": ("P2001", "prof1234"),
}

DAY_NAMES = ["월", "화", "수", "목", "금"]

# 주간 시간표용 구조화된 수업 시간. day: 0=월 … 4=금.
MEETINGS = {
    "CSE311": [{"day": 0, "start": "10:00", "end": "11:15"},
               {"day": 2, "start": "10:00", "end": "11:15"}],
    "CSE245": [{"day": 1, "start": "13:00", "end": "14:15"},
               {"day": 3, "start": "13:00", "end": "14:15"}],
    "GEN102": [{"day": 4, "start": "09:00", "end": "11:45"}],
}

STATUS_LABELS = {
    "present": "출석",
    "late": "지각",
    "absent": "결석",
    "open": "미제출",
    "submitted": "제출 완료",
    "graded": "채점 완료",
}


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _with_ids(rows: list[dict]) -> list[dict]:
    """DB 의 identity 컬럼처럼 1부터 id 를 붙인다."""
    return [{**r, "id": i} for i, r in enumerate(rows, start=1)]


def sample_tables() -> dict[str, list[dict]]:
    """DB 테이블과 같은 모양의 샘플 데이터를 새로 만들어 돌려준다."""
    users = _with_ids([
        {"login_id": l, "password": p, "role": r, "name": n, "department": dep, "semester": SEMESTER}
        for l, p, r, n, dep in [
            ("P2001", "prof1234", "professor", "박지우", "컴퓨터공학과"),
            ("P2002", "prof1234", "professor", "이서연", "컴퓨터공학과"),
            ("P2003", "prof1234", "professor", "정민호", "교양대학"),
            ("202512345", "student1234", "student", "김한결", "컴퓨터공학과"),
            ("202512346", "student1234", "student", "이도윤", "컴퓨터공학과"),
            ("202512347", "student1234", "student", "최서윤", "컴퓨터공학과"),
        ]
    ])
    uid = {u["login_id"]: u["id"] for u in users}

    courses = [
        {"id": cid, "title": title, "professor_id": uid[prof], "schedule": sched, "room": room,
         "card_color": color, "course_code": code, "sort_order": order}
        for cid, title, prof, sched, room, color, code, order in [
            ("CSE311", "운영체제", "P2001", "월·수 10:00–11:15", "공학관 401", "#3b5bdb", "0001765003", 1),
            ("CSE245", "자료구조", "P2002", "화·목 13:00–14:15", "공학관 207", "#2f9e44", "0001772003", 2),
            ("GEN102", "글쓰기와 커뮤니케이션", "P2003", "금 09:00–11:45", "인문관 115", "#e8590c", "0000936039", 3),
        ]
    ]

    enrollments = _with_ids([
        {"course_id": c, "student_id": uid[l]}
        for c, l in [
            ("CSE311", "202512345"), ("CSE245", "202512345"), ("GEN102", "202512345"),
            ("CSE311", "202512346"), ("CSE245", "202512346"),
            ("CSE311", "202512347"), ("GEN102", "202512347"),
        ]
    ])

    materials = _with_ids([
        {"course_id": c, "week": w, "title": t, "type": ty, "size_kb": kb, "posted": _d(p)}
        for c, w, t, ty, kb, p in [
            ("CSE311", 1, "강의 개요와 운영체제의 역할", "PDF", 1240, "2026-03-09"),
            ("CSE311", 2, "프로세스와 스레드", "PDF", 2010, "2026-03-16"),
            ("CSE311", 3, "CPU 스케줄링", "PDF", 1875, "2026-03-23"),
            ("CSE311", 4, "동기화와 교착 상태", "슬라이드", 3320, "2026-03-30"),
            ("CSE311", 5, "메모리 관리 기법", "PDF", 2460, "2026-04-06"),
            ("CSE245", 1, "복잡도 분석과 빅오 표기법", "PDF", 980, "2026-03-10"),
            ("CSE245", 2, "배열과 연결 리스트", "PDF", 1530, "2026-03-17"),
            ("CSE245", 3, "스택과 큐", "슬라이드", 2140, "2026-03-24"),
            ("CSE245", 4, "트리와 이진 탐색 트리", "PDF", 2680, "2026-04-07"),
            ("GEN102", 1, "학술적 글쓰기의 기초", "PDF", 760, "2026-03-11"),
            ("GEN102", 2, "논증 구조 세우기", "PDF", 1120, "2026-03-25"),
            ("GEN102", 3, "자료 인용과 출처 표기", "슬라이드", 1890, "2026-04-08"),
        ]
    ])

    assignments = [
        {"id": aid, "course_id": c, "title": t, "due": _d(due), "points": pts}
        for aid, c, t, due, pts in [
            ("CSE311-A1", "CSE311", "프로세스 상태 전이도 작성", "2026-04-03", 20),
            ("CSE311-A2", "CSE311", "라운드로빈 스케줄러 구현", "2026-04-15", 30),
            ("CSE311-A3", "CSE311", "교착 상태 탐지 보고서", "2026-04-22", 25),
            ("CSE245-A1", "CSE245", "연결 리스트 ADT 구현", "2026-03-29", 20),
            ("CSE245-A2", "CSE245", "이진 탐색 트리 순회", "2026-04-18", 25),
            ("GEN102-A1", "GEN102", "주제문 초안 제출", "2026-04-10", 15),
            ("GEN102-A2", "GEN102", "에세이 1차 원고", "2026-04-25", 30),
        ]
    ]

    submissions = _with_ids([
        {"assignment_id": a, "student_id": uid[l], "status": st, "score": sc, "late": late,
         "submitted_at": _d(d)}
        for a, l, st, sc, late, d in [
            ("CSE311-A1", "202512345", "graded", 18, False, "2026-04-02"),
            ("CSE311-A2", "202512345", "submitted", None, False, "2026-04-12"),
            ("CSE245-A1", "202512345", "graded", 20, False, "2026-03-28"),
            ("CSE311-A1", "202512346", "graded", 15, False, "2026-04-03"),
            ("CSE311-A2", "202512346", "submitted", None, False, "2026-04-11"),
            ("CSE245-A1", "202512346", "graded", 17, False, "2026-03-29"),
            ("CSE245-A2", "202512346", "submitted", None, False, "2026-04-12"),
            ("CSE311-A1", "202512347", "graded", 20, False, "2026-04-01"),
            ("CSE311-A2", "202512347", "submitted", None, False, "2026-04-12"),
            ("GEN102-A1", "202512347", "submitted", None, True, "2026-04-11"),
        ]
    ])

    # 과목별 첫 수업 날짜 + 7일씩 = 주차별 수업일.
    base = {"CSE311": _d("2026-03-09"), "CSE245": _d("2026-03-10"), "GEN102": _d("2026-03-11")}
    attendance_rows = []
    for c, l, statuses in [
        ("CSE311", "202512345", ["present", "present", "present", "late", "present"]),
        ("CSE245", "202512345", ["present", "present", "absent", "present"]),
        ("GEN102", "202512345", ["present", "present", "present"]),
        ("CSE311", "202512346", ["present", "late", "present", "present", "present"]),
        ("CSE245", "202512346", ["present", "late", "present", "present"]),
        ("CSE311", "202512347", ["present", "present", "absent", "present", "present"]),
        ("GEN102", "202512347", ["present", "present", "late"]),
    ]:
        for w, status in enumerate(statuses, start=1):
            attendance_rows.append({
                "course_id": c, "student_id": uid[l], "week": w,
                "date": date.fromordinal(base[c].toordinal() + 7 * (w - 1)), "status": status,
            })
    attendance = _with_ids(attendance_rows)

    announcements = _with_ids([
        {"course_id": c, "author_id": uid[a] if a else None, "title": t, "body": b,
         "posted": _d(p), "pinned": pin}
        for c, a, t, b, p, pin in [
            (None, None, "중간고사 기간 도서관 24시간 개방 안내",
             "중간고사 기간 동안 중앙도서관을 24시간 개방합니다.", "2026-04-11", True),
            ("CSE311", "P2001", "4주차 보강 안내",
             "지난주 휴강분 보강을 금요일 16시 공학관 401에서 진행합니다.", "2026-04-09", False),
            ("CSE311", "P2001", "과제 2 제출 형식 공지",
             "라운드로빈 스케줄러는 소스와 실행 캡처를 zip으로 묶어 제출하세요.", "2026-04-07", False),
            ("CSE245", "P2002", "실습실 PC 사용 안내",
             "자료구조 실습은 공학관 207 실습 PC에서도 가능합니다.", "2026-04-05", False),
            ("GEN102", "P2003", "에세이 분량 기준",
             "1차 원고는 A4 3~4매 분량으로 작성합니다.", "2026-04-08", False),
        ]
    ])

    exams = _with_ids([
        {"course_id": c, "student_id": uid[l], "name": "중간고사", "score": sc, "max": 50, "date": _d(d)}
        for c, l, sc, d in [
            ("CSE311", "202512345", 42, "2026-04-12"), ("CSE245", "202512345", 47, "2026-04-11"),
            ("CSE311", "202512346", 38, "2026-04-12"), ("CSE245", "202512346", 41, "2026-04-11"),
            ("CSE311", "202512347", 45, "2026-04-12"),
        ]
    ])

    lectures = _with_ids([
        {"course_id": c, "week": w, "title": t, "duration_min": m}
        for c, w, t, m in [
            ("CSE311", 1, "운영체제란 무엇인가", 48), ("CSE311", 2, "프로세스 생성과 종료", 52),
            ("CSE311", 3, "스케줄링 알고리즘 비교", 45), ("CSE311", 4, "세마포어와 뮤텍스", 50),
            ("CSE245", 1, "빅오 표기법 직관", 38), ("CSE245", 2, "연결 리스트 구현", 41),
            ("CSE245", 3, "스택으로 괄호 검사", 35),
            ("GEN102", 1, "좋은 글의 조건", 30), ("GEN102", 2, "논증과 근거", 33),
        ]
    ])
    lecture_id = {(r["course_id"], r["week"]): r["id"] for r in lectures}

    progress_rows = []
    for c, l, pcts in [
        ("CSE311", "202512345", [100, 100, 60, 0]),
        ("CSE245", "202512345", [100, 80, 0]),
        ("GEN102", "202512345", [100, 50]),
        ("CSE311", "202512346", [100, 70, 0, 0]),
        ("CSE245", "202512346", [100, 100, 40]),
        ("CSE311", "202512347", [100, 100, 100, 30]),
        ("GEN102", "202512347", [100, 100]),
    ]:
        for w, pct in enumerate(pcts, start=1):
            progress_rows.append({
                "lecture_id": lecture_id[(c, w)], "student_id": uid[l], "watched_pct": pct,
            })
    lecture_progress = _with_ids(progress_rows)

    qna = _with_ids([
        {"course_id": "CSE311", "author_id": uid["202512345"], "author": "김한결",
         "title": "라운드로빈 타임 퀀텀 값 질문",
         "body": "과제 2에서 타임 퀀텀은 고정값으로 두면 되나요?", "posted": _d("2026-04-10"),
         "answered": True},
        {"course_id": "CSE245", "author_id": uid["202512346"], "author": "이도윤",
         "title": "BST 중복 키 처리",
         "body": "이진 탐색 트리에 중복 키가 들어오면 어떻게 처리하나요?", "posted": _d("2026-04-12"),
         "answered": False},
    ])
    qna_replies = _with_ids([
        {"qna_id": 1, "author_id": uid["P2001"], "author": "박지우 교수",
         "body": "네, 4ms로 고정해서 구현하세요."},
    ])

    return {
        "lms_users": users,
        "lms_courses": courses,
        "lms_enrollments": enrollments,
        "lms_materials": materials,
        "lms_assignments": assignments,
        "lms_submissions": submissions,
        "lms_attendance": attendance,
        "lms_announcements": announcements,
        "lms_exams": exams,
        "lms_lectures": lectures,
        "lms_lecture_progress": lecture_progress,
        "lms_qna": qna,
        "lms_qna_replies": qna_replies,
    }
