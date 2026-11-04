"""클래스허브 — 독자 설계 LMS 데모.

과제 제출, 강의 자료 열람, 출석 확인을 한 화면에서 보여주는 학습관리시스템
데모다. 실제 서비스가 아니며 모든 데이터는 가상이다.

데이터는 Supabase 백엔드(``data.db``)에서 읽고 쓴다. 자격 증명이 없으면
가상 샘플 데이터로 폴백하며, 이때는 변경 사항이 세션에만 남는다.

실행:  streamlit run src/main.py
"""

from __future__ import annotations

import html as _html

import streamlit as st

from data import db
from data.sample import DAY_NAMES, MEETINGS, STATUS_LABELS, TODAY

st.set_page_config(page_title="클래스허브 LMS", page_icon="🎓", layout="wide")

# 좌측 네비게이션 항목 — (페이지 이름, 아이콘). 순서가 메뉴 순서다.
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

# 사이드바 라디오를 아이콘 버튼처럼 보이게 하는 스타일.
_NAV_CSS = """
<style>
section[data-testid="stSidebar"] div[role="radiogroup"]{gap:4px}
section[data-testid="stSidebar"] div[role="radiogroup"] label{
  padding:9px 12px;border-radius:10px;margin:0;transition:background .12s;cursor:pointer}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{
  background:rgba(59,91,219,.08)}
section[data-testid="stSidebar"] div[role="radiogroup"] label p{
  font-size:15px;font-weight:500}
/* 기본 라디오 동그라미 숨기고 아이콘+글자만 */
section[data-testid="stSidebar"] div[role="radiogroup"] label > div > div:first-child{display:none}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){
  background:rgba(59,91,219,.14)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p{
  color:#3b5bdb;font-weight:700}
</style>
"""


# ----------------------------------------------------------------------------
# 상태 로드 — Supabase 백엔드에서 읽어 세션에 채운다.
#   · 연결됨: 매 실행마다 새로 로드(DB가 진실의 원천).
#   · 폴백: 최초 1회만 로드하고 이후 세션 수정으로 데모 상호작용 유지.
# ----------------------------------------------------------------------------
def load_state() -> None:
    connected = db.is_connected()
    if connected or "courses" not in st.session_state:
        state = db.load_all()
        for key, value in state.items():
            st.session_state[key] = value
    st.session_state.connected = connected


def _connected() -> bool:
    return st.session_state.get("connected", False)


def find_course(course_id: str) -> dict:
    return next(c for c in st.session_state.courses if c["id"] == course_id)


def all_assignments() -> list[dict]:
    """과목 정보를 붙인 전체 과제 목록."""
    rows = []
    for course in st.session_state.courses:
        for a in course["assignments"]:
            rows.append({**a, "course_id": course["id"], "course_title": course["title"]})
    return rows


def dday(due) -> int:
    return (due - TODAY).days


def dday_label(due) -> str:
    n = dday(due)
    if n == 0:
        return "오늘 마감"
    if n > 0:
        return f"D-{n}"
    return f"{-n}일 지남"


# ----------------------------------------------------------------------------
# 사이드바
# ----------------------------------------------------------------------------
def sidebar() -> str:
    with st.sidebar:
        st.markdown("### 🎓 클래스허브")
        st.caption("학습관리시스템 데모")
        st.divider()

        s = st.session_state.student
        st.markdown(f"**{s['name']}**")
        st.caption(f"{s['major']} · {s['student_id']}")
        st.caption(s["semester"])
        st.divider()

        st.markdown(_NAV_CSS, unsafe_allow_html=True)
        display = st.radio(
            "메뉴",
            [f"{icon} {name}" for name, icon in NAV_ITEMS],
            label_visibility="collapsed",
        )
        # 아이콘을 뗀 순수 페이지 이름으로 되돌린다.
        page = display.split(" ", 1)[1]
        st.divider()
        st.caption(f"오늘: {TODAY:%Y-%m-%d}")
        if _connected():
            st.caption("🟢 Supabase 백엔드 연결됨")
        else:
            st.caption("🟠 샘플 데이터(백엔드 미연결)")
        st.caption("⚠️ 데모 — 모든 데이터는 가상입니다.")
    return page


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
    pending = [a for a in assignments if a["status"] in ("open", "late")]
    upcoming = sorted(
        [a for a in pending if dday(a["due"]) >= 0], key=lambda a: a["due"]
    )
    overdue = [a for a in pending if dday(a["due"]) < 0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("수강 과목", f"{len(st.session_state.courses)}개")
    c2.metric("제출할 과제", f"{len(pending)}개")
    c3.metric("마감 지난 과제", f"{len(overdue)}개")
    avg_rate = sum(attendance_rate(c["id"]) for c in st.session_state.courses) / len(
        st.session_state.courses
    )
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
            if st.button("열람", key=f"view-{course['id']}-{m['week']}"):
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
        rows = [
            a
            for a in all_assignments()
            if a["status"] in ("open", "late")
        ]
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
                    if _connected():
                        db.submit_assignment(a["id"])
                    else:
                        _mark_submitted(a["course_id"], a["id"])
                    st.toast(f"'{a['title']}' 제출 완료!")
                    st.rerun()

    with tab_done:
        rows = [
            a
            for a in all_assignments()
            if a["status"] in ("submitted", "graded")
        ]
        rows.sort(key=lambda a: a["due"], reverse=True)
        if not rows:
            st.info("아직 제출하거나 채점된 과제가 없습니다.")
        for a in rows:
            score = (
                f"{a['score']}/{a['points']}점"
                if a["status"] == "graded"
                else "채점 대기"
            )
            st.markdown(
                f"**{a['course_title']} — {a['title']}**  \n"
                f"{STATUS_LABELS[a['status']]} · {score} · 마감 {a['due']:%m/%d}"
            )
            st.divider()


def _mark_submitted(course_id: str, assignment_id: str) -> None:
    """폴백 모드 — 세션 상태의 과제를 제출 완료로 표시."""
    course = find_course(course_id)
    for a in course["assignments"]:
        if a["id"] == assignment_id:
            a["status"] = "submitted"


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
                if _connected():
                    db.check_attendance(course["id"], next_week, TODAY, "present")
                else:
                    records.append(
                        {"week": next_week, "date": TODAY, "status": "present"}
                    )
                st.toast(f"{course['title']} {next_week}주차 출석 완료!")
                st.rerun()


# ----------------------------------------------------------------------------
# 페이지: 수강 강좌 (카드 그리드 홈)
# ----------------------------------------------------------------------------
_CARD_CSS = """
<style>
.course-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
  gap:18px;margin-top:6px}
.course-card{border:1px solid #e9ecef;border-radius:14px;overflow:hidden;background:#fff;
  box-shadow:0 1px 3px rgba(0,0,0,.07);transition:transform .12s,box-shadow .12s}
.course-card:hover{transform:translateY(-3px);box-shadow:0 8px 22px rgba(0,0,0,.12)}
.course-head{height:118px;position:relative;
  background:linear-gradient(135deg,var(--c) 0%,color-mix(in srgb,var(--c) 68%,#000) 100%)}
.course-head::before{content:"";position:absolute;inset:0;opacity:.35;
  background:repeating-linear-gradient(115deg,transparent 0 22px,rgba(255,255,255,.14) 22px 23px)}
.course-head::after{content:"";position:absolute;inset:0;
  background:radial-gradient(circle at 72% 28%,rgba(255,255,255,.30),transparent 55%)}
.course-body{padding:14px 16px 16px}
.course-meta{font-size:12px;color:#868e96;margin-bottom:6px}
.course-title{font-weight:700;font-size:15px;line-height:1.35;color:#212529}
.course-title .code{font-weight:400;color:#adb5bd;font-size:13px}
.course-prof{display:flex;align-items:center;gap:8px;margin-top:16px;font-size:13px;color:#495057}
.course-ava{display:inline-flex;align-items:center;justify-content:center;width:27px;height:27px;
  border-radius:50%;background:color-mix(in srgb,var(--c) 16%,#fff);color:var(--c);
  font-weight:700;font-size:12px;flex:0 0 auto}
</style>
"""


def page_my_courses() -> None:
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    courses = st.session_state.courses
    student = st.session_state.student
    card_colors = st.session_state.card_colors
    course_code = st.session_state.course_code
    st.title("수강 강좌")
    st.caption(f"{student['semester']} · 수강 중인 강좌 {len(courses)}개")

    cards = ['<div class="course-grid">']
    for c in courses:
        color = card_colors.get(c["id"], "#3b5bdb")
        code = course_code.get(c["id"], c["id"])
        prof = c["professor"]
        title = _html.escape(c["title"])
        cards.append(
            f'<div class="course-card">'
            f'<div class="course-head" style="--c:{color}"></div>'
            f'<div class="course-body">'
            f'<div class="course-meta">{student["semester"]} · 교과과정</div>'
            f'<div class="course-title">{title} '
            f'<span class="code">({code})</span></div>'
            f'<div class="course-prof" style="--c:{color}">'
            f'<span class="course-ava">{_html.escape(prof[0])}</span>'
            f'{_html.escape(prof)}</div>'
            f'</div></div>'
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)

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
    rows.sort(key=lambda a: (not a["pinned"], _neg_date(a["posted"])))
    for a in rows:
        scope = "전체" if a["course_id"] is None else course_name.get(a["course_id"], "")
        with st.container(border=True):
            head = "📌 " if a["pinned"] else ""
            st.markdown(f"{head}**{a['title']}**")
            st.caption(f"[{scope}] · {a['posted']:%Y-%m-%d}")
            st.write(a["body"])


def _neg_date(d):
    """최신 날짜가 먼저 오도록 정렬 키로 쓸 음수 서수."""
    return -d.toordinal()


# ----------------------------------------------------------------------------
# 페이지: 온라인 강의
# ----------------------------------------------------------------------------
def page_lectures() -> None:
    st.title("온라인 강의")
    st.caption("강의 영상 시청 진도를 확인하고 이어서 봅니다.")

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
                    if _connected():
                        db.watch_lecture(v["id"])
                    else:
                        v["watched_pct"] = 100
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
# 페이지: 시간표
# ----------------------------------------------------------------------------
def page_timetable() -> None:
    st.title("시간표")
    st.caption("이번 학기 주간 시간표입니다.")

    name = {c["id"]: c["title"] for c in st.session_state.courses}
    room = {c["id"]: c["room"] for c in st.session_state.courses}

    # 교시 행: 수업이 걸친 시간대를 1시간 단위로 09~15시까지.
    hours = list(range(9, 15))
    header = st.columns([1] + [2] * len(DAY_NAMES))
    header[0].markdown("**시간**")
    for i, d in enumerate(DAY_NAMES):
        header[i + 1].markdown(f"**{d}**")

    for h in hours:
        row = st.columns([1] + [2] * len(DAY_NAMES))
        row[0].markdown(f"{h:02d}:00")
        for di in range(len(DAY_NAMES)):
            cell = ""
            for cid, meets in MEETINGS.items():
                for m in meets:
                    if m["day"] == di and int(m["start"][:2]) == h and cid in name:
                        cell = f"**{name[cid]}**  \n{room[cid]}"
            row[di + 1].markdown(cell if cell else " ")
        st.divider()


# ----------------------------------------------------------------------------
# 페이지: Q&A 게시판
# ----------------------------------------------------------------------------
def page_qna() -> None:
    st.title("Q&A 게시판")
    st.caption("과목별로 질문을 올리고 답변을 확인합니다.")

    titles = {c["title"]: c["id"] for c in st.session_state.courses}
    chosen = st.selectbox("과목 선택", list(titles.keys()))
    cid = titles[chosen]

    with st.form("new_question", clear_on_submit=True):
        st.markdown("**새 질문 작성**")
        q_title = st.text_input("제목")
        q_body = st.text_area("내용")
        if st.form_submit_button("질문 등록", type="primary"):
            if q_title.strip():
                if _connected():
                    db.add_question(cid, q_title.strip(), q_body.strip(), TODAY)
                else:
                    st.session_state.qna.append(
                        {
                            "id": f"Q{len(st.session_state.qna) + 1}",
                            "course_id": cid,
                            "author": "학생",
                            "title": q_title.strip(),
                            "body": q_body.strip(),
                            "posted": TODAY,
                            "answered": False,
                            "replies": [],
                        }
                    )
                st.toast("질문을 등록했습니다.")
                st.rerun()
            else:
                st.warning("제목을 입력하세요.")

    st.divider()
    posts = [q for q in st.session_state.qna if q["course_id"] == cid]
    posts.sort(key=lambda q: _neg_date(q["posted"]))
    if not posts:
        st.info("아직 등록된 질문이 없습니다.")
    for q in posts:
        badge = "✅ 답변 완료" if q["answered"] else "🟡 답변 대기"
        with st.expander(f"{badge} · {q['title']}"):
            st.caption(f"{q['author']} · {q['posted']:%Y-%m-%d}")
            st.write(q["body"] or "_(내용 없음)_")
            for r in q["replies"]:
                st.markdown(f"> **{r['author']}**: {r['body']}")


# ----------------------------------------------------------------------------
# 라우팅
# ----------------------------------------------------------------------------
def main() -> None:
    load_state()
    page = sidebar()
    {
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
    }[page]()


if __name__ == "__main__":
    main()
