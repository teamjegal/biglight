"""데모용 샘플 데이터.

실제 서비스가 아니라 화면을 채우기 위한 가짜 데이터다. 모든 이름과 과목은
가상의 것이며, 특정 학교나 기관과 관련이 없다. 세션 상태 초기화에 쓰인다.
"""

from __future__ import annotations

from datetime import date, timedelta

# 데모를 여는 '오늘'을 고정해 화면이 항상 같은 상태로 보이게 한다.
TODAY = date(2026, 4, 13)


def _d(offset_days: int) -> date:
    """TODAY 기준 상대 날짜."""
    return TODAY + timedelta(days=offset_days)


DEMO_STUDENT = {
    "name": "김한결",
    "student_id": "202512345",
    "major": "컴퓨터공학과",
    "semester": "2026학년도 1학기",
}

# 수강 과목. 각 과목은 주차별 강의 자료, 과제, 출석 기록을 가진다.
COURSES = [
    {
        "id": "CSE311",
        "title": "운영체제",
        "professor": "박지우",
        "schedule": "월·수 10:00–11:15",
        "room": "공학관 401",
        "materials": [
            {"week": 1, "title": "강의 개요와 운영체제의 역할", "type": "PDF", "size_kb": 1240, "posted": _d(-35)},
            {"week": 2, "title": "프로세스와 스레드", "type": "PDF", "size_kb": 2010, "posted": _d(-28)},
            {"week": 3, "title": "CPU 스케줄링", "type": "PDF", "size_kb": 1875, "posted": _d(-21)},
            {"week": 4, "title": "동기화와 교착 상태", "type": "슬라이드", "size_kb": 3320, "posted": _d(-14)},
            {"week": 5, "title": "메모리 관리 기법", "type": "PDF", "size_kb": 2460, "posted": _d(-7)},
        ],
        "assignments": [
            {"id": "CSE311-A1", "title": "프로세스 상태 전이도 작성", "due": _d(-10), "points": 20, "status": "graded", "score": 18},
            {"id": "CSE311-A2", "title": "라운드로빈 스케줄러 구현", "due": _d(2), "points": 30, "status": "submitted", "score": None},
            {"id": "CSE311-A3", "title": "교착 상태 탐지 보고서", "due": _d(9), "points": 25, "status": "open", "score": None},
        ],
    },
    {
        "id": "CSE245",
        "title": "자료구조",
        "professor": "이서연",
        "schedule": "화·목 13:00–14:15",
        "room": "공학관 207",
        "materials": [
            {"week": 1, "title": "복잡도 분석과 빅오 표기법", "type": "PDF", "size_kb": 980, "posted": _d(-34)},
            {"week": 2, "title": "배열과 연결 리스트", "type": "PDF", "size_kb": 1530, "posted": _d(-27)},
            {"week": 3, "title": "스택과 큐", "type": "슬라이드", "size_kb": 2140, "posted": _d(-20)},
            {"week": 4, "title": "트리와 이진 탐색 트리", "type": "PDF", "size_kb": 2680, "posted": _d(-6)},
        ],
        "assignments": [
            {"id": "CSE245-A1", "title": "연결 리스트 ADT 구현", "due": _d(-15), "points": 20, "status": "graded", "score": 20},
            {"id": "CSE245-A2", "title": "이진 탐색 트리 순회", "due": _d(5), "points": 25, "status": "open", "score": None},
        ],
    },
    {
        "id": "GEN102",
        "title": "글쓰기와 커뮤니케이션",
        "professor": "정민호",
        "schedule": "금 09:00–11:45",
        "room": "인문관 115",
        "materials": [
            {"week": 1, "title": "학술적 글쓰기의 기초", "type": "PDF", "size_kb": 760, "posted": _d(-33)},
            {"week": 2, "title": "논증 구조 세우기", "type": "PDF", "size_kb": 1120, "posted": _d(-19)},
            {"week": 3, "title": "자료 인용과 출처 표기", "type": "슬라이드", "size_kb": 1890, "posted": _d(-5)},
        ],
        "assignments": [
            {"id": "GEN102-A1", "title": "주제문 초안 제출", "due": _d(-3), "points": 15, "status": "late", "score": None},
            {"id": "GEN102-A2", "title": "에세이 1차 원고", "due": _d(12), "points": 30, "status": "open", "score": None},
        ],
    },
]

# 과목별 출석 기록. 각 주차 = 한 번의 수업. 상태: present / late / absent.
ATTENDANCE = {
    "CSE311": [
        {"week": w, "date": _d(-35 + (w - 1) * 7), "status": s}
        for w, s in enumerate(["present", "present", "present", "late", "present"], start=1)
    ],
    "CSE245": [
        {"week": w, "date": _d(-34 + (w - 1) * 7), "status": s}
        for w, s in enumerate(["present", "present", "absent", "present"], start=1)
    ],
    "GEN102": [
        {"week": w, "date": _d(-33 + (w - 1) * 7), "status": s}
        for w, s in enumerate(["present", "present", "present"], start=1)
    ],
}

STATUS_LABELS = {
    "present": "출석",
    "late": "지각",
    "absent": "결석",
    "open": "미제출",
    "submitted": "제출 완료",
    "graded": "채점 완료",
}


# ---------------------------------------------------------------------------
# 확장 데이터 — 공지, 시간표, 성적(시험), 온라인 강의, Q&A 게시판.
# 모두 가상이며, 과목 id로 묶인다(ATTENDANCE와 동일한 방식).
# ---------------------------------------------------------------------------

# 주간 시간표용 구조화된 수업 시간. day: 0=월 … 4=금.
MEETINGS = {
    "CSE311": [{"day": 0, "start": "10:00", "end": "11:15"},
               {"day": 2, "start": "10:00", "end": "11:15"}],
    "CSE245": [{"day": 1, "start": "13:00", "end": "14:15"},
               {"day": 3, "start": "13:00", "end": "14:15"}],
    "GEN102": [{"day": 4, "start": "09:00", "end": "11:45"}],
}

DAY_NAMES = ["월", "화", "수", "목", "금"]

# 공지사항. course_id가 None이면 전체 공지.
ANNOUNCEMENTS = [
    {"course_id": None, "title": "중간고사 기간 도서관 24시간 개방 안내",
     "body": "중간고사 기간 동안 중앙도서관을 24시간 개방합니다.",
     "posted": _d(-2), "pinned": True},
    {"course_id": "CSE311", "title": "4주차 보강 안내",
     "body": "지난주 휴강분 보강을 금요일 16시 공학관 401에서 진행합니다.",
     "posted": _d(-4), "pinned": False},
    {"course_id": "CSE311", "title": "과제 2 제출 형식 공지",
     "body": "라운드로빈 스케줄러는 소스와 실행 캡처를 zip으로 묶어 제출하세요.",
     "posted": _d(-6), "pinned": False},
    {"course_id": "CSE245", "title": "실습실 PC 사용 안내",
     "body": "자료구조 실습은 공학관 207 실습 PC에서도 가능합니다.",
     "posted": _d(-8), "pinned": False},
    {"course_id": "GEN102", "title": "에세이 분량 기준",
     "body": "1차 원고는 A4 3~4매 분량으로 작성합니다.",
     "posted": _d(-5), "pinned": False},
]

# 시험 성적. 과제 점수와 합쳐 성적 페이지에서 과목 총점을 낸다.
EXAMS = {
    "CSE311": [{"name": "중간고사", "score": 42, "max": 50, "date": _d(-1)}],
    "CSE245": [{"name": "중간고사", "score": 47, "max": 50, "date": _d(-2)}],
    "GEN102": [],
}

# 온라인 강의 영상. watched_pct = 시청 진도(%).
LECTURES = {
    "CSE311": [
        {"week": 1, "title": "운영체제란 무엇인가", "duration_min": 48, "watched_pct": 100},
        {"week": 2, "title": "프로세스 생성과 종료", "duration_min": 52, "watched_pct": 100},
        {"week": 3, "title": "스케줄링 알고리즘 비교", "duration_min": 45, "watched_pct": 60},
        {"week": 4, "title": "세마포어와 뮤텍스", "duration_min": 50, "watched_pct": 0},
    ],
    "CSE245": [
        {"week": 1, "title": "빅오 표기법 직관", "duration_min": 38, "watched_pct": 100},
        {"week": 2, "title": "연결 리스트 구현", "duration_min": 41, "watched_pct": 80},
        {"week": 3, "title": "스택으로 괄호 검사", "duration_min": 35, "watched_pct": 0},
    ],
    "GEN102": [
        {"week": 1, "title": "좋은 글의 조건", "duration_min": 30, "watched_pct": 100},
        {"week": 2, "title": "논증과 근거", "duration_min": 33, "watched_pct": 50},
    ],
}

# Q&A 게시판. 과목별 질문과 답변(강사/학생).
QNA = [
    {"id": "Q1", "course_id": "CSE311", "author": "학생", "title": "라운드로빈 타임 퀀텀 값 질문",
     "body": "과제 2에서 타임 퀀텀은 고정값으로 두면 되나요?",
     "posted": _d(-3), "answered": True,
     "replies": [{"author": "박지우 교수", "body": "네, 4ms로 고정해서 구현하세요."}]},
    {"id": "Q2", "course_id": "CSE245", "author": "학생", "title": "BST 중복 키 처리",
     "body": "이진 탐색 트리에 중복 키가 들어오면 어떻게 처리하나요?",
     "posted": _d(-1), "answered": False, "replies": []},
]


# ---------------------------------------------------------------------------
# 강좌 카드 홈용 메타 — 카드 헤더 색상과 학수번호(가상).
# ---------------------------------------------------------------------------
CARD_COLORS = {
    "CSE311": "#3b5bdb",  # 파랑
    "CSE245": "#2f9e44",  # 초록
    "GEN102": "#e8590c",  # 주황
}

COURSE_CODE = {
    "CSE311": "0001765003",
    "CSE245": "0001772003",
    "GEN102": "0000936039",
}
