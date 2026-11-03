# biglight

## 폴더 구조

```
biglight/
├── .streamlit/
│   └── secrets.toml      # API 키 및 DB 연동 정보 (Git 미업로드)
├── src/
│   ├── main.py           # Streamlit 메인 실행 파일 (UI 화면)
│   ├── ai.py             # AI 연동 및 백엔드 로직
│   └── components/       # 재사용 가능한 UI 조각들
├── .env.example          # 환경 변수 예시
├── CLAUDE.md             # AI 에이전트/개발 협업 규칙
└── requirements.txt      # 파이썬 라이브러리 목록
```

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/main.py
```

비밀 값은 `.streamlit/secrets.toml`에 넣습니다(커밋 금지). 협업 규칙은 [CLAUDE.md](CLAUDE.md)를 참고하세요.
