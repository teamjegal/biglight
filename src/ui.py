"""학생·교수 화면이 함께 쓰는 UI 조각 — 사이드바, 강좌 카드, 시간표, 날짜 헬퍼."""

from __future__ import annotations

import html as _html
from typing import Callable

import streamlit as st

from data import db
from data.sample import DAY_NAMES, MEETINGS, TODAY

# 사이드바 라디오를 아이콘 버튼처럼 보이게 하는 스타일.
NAV_CSS = """
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

CARD_CSS = """
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


# ----------------------------------------------------------------------------
# 날짜 헬퍼
# ----------------------------------------------------------------------------
def dday(due) -> int:
    return (due - TODAY).days


def dday_label(due) -> str:
    n = dday(due)
    if n == 0:
        return "오늘 마감"
    if n > 0:
        return f"D-{n}"
    return f"{-n}일 지남"


def neg_date(d) -> int:
    """최신 날짜가 먼저 오도록 정렬 키로 쓸 음수 서수."""
    return -d.toordinal()


# ----------------------------------------------------------------------------
# 로그아웃 / 사이드바
# ----------------------------------------------------------------------------
def logout() -> None:
    """로그인 상태와 화면 데이터를 지운다(샘플 모드의 메모리 데이터는 유지)."""
    for key in list(st.session_state.keys()):
        if key != "_mem_tables":
            del st.session_state[key]
    st.rerun()


def sidebar(nav_items: list[tuple[str, str]], name: str, lines: list[str], role_label: str) -> str:
    """역할별 메뉴 사이드바. 선택된 페이지 이름을 돌려준다."""
    with st.sidebar:
        st.markdown("### 🎓 클래스허브")
        st.caption(f"학습관리시스템 데모 · {role_label}")
        st.divider()

        st.markdown(f"**{name}**")
        for line in lines:
            st.caption(line)
        if st.button("로그아웃", key="logout", use_container_width=True):
            logout()
        st.divider()

        st.markdown(NAV_CSS, unsafe_allow_html=True)
        display = st.radio(
            "메뉴",
            [f"{icon} {label}" for label, icon in nav_items],
            label_visibility="collapsed",
        )
        # 아이콘을 뗀 순수 페이지 이름으로 되돌린다.
        page = display.split(" ", 1)[1]
        st.divider()
        st.caption(f"오늘: {TODAY:%Y-%m-%d}")
        if db.is_connected():
            st.caption("🟢 Supabase 백엔드 연결됨")
        else:
            st.caption("🟠 샘플 데이터(백엔드 미연결)")
        st.caption("⚠️ 데모 — 모든 데이터는 가상입니다.")
    return page


# ----------------------------------------------------------------------------
# 강좌 카드 그리드
# ----------------------------------------------------------------------------
def course_cards(
    courses: list[dict],
    colors: dict,
    codes: dict,
    semester: str,
    footer: Callable[[dict], tuple[str, str]],
) -> None:
    """강좌 카드 그리드. footer(course) -> (아바타 글자, 하단 문구)."""
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    cards = ['<div class="course-grid">']
    for c in courses:
        color = colors.get(c["id"], "#3b5bdb")
        code = codes.get(c["id"], c["id"])
        avatar, label = footer(c)
        cards.append(
            f'<div class="course-card">'
            f'<div class="course-head" style="--c:{color}"></div>'
            f'<div class="course-body">'
            f'<div class="course-meta">{_html.escape(semester)} · 교과과정</div>'
            f'<div class="course-title">{_html.escape(c["title"])} '
            f'<span class="code">({_html.escape(code)})</span></div>'
            f'<div class="course-prof" style="--c:{color}">'
            f'<span class="course-ava">{_html.escape(avatar)}</span>'
            f'{_html.escape(label)}</div>'
            f'</div></div>'
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# 주간 시간표
# ----------------------------------------------------------------------------
def timetable(courses: list[dict]) -> None:
    st.title("시간표")
    st.caption("이번 학기 주간 시간표입니다.")

    name = {c["id"]: c["title"] for c in courses}
    room = {c["id"]: c["room"] for c in courses}

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
