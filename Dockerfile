# 클래스허브 LMS — 배포용 컨테이너 (Azure·Render·Fly·Railway·Heroku 컨테이너 등 어디서든).
# CI 와 같은 파이썬 버전(3.12)을 쓴다.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # 공개 배포 기본값: '데모 계정으로 바로 둘러보기' 버튼(관리자 로그인 포함)을 숨긴다.
    HIDE_DEMO_LOGINS=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY .streamlit/config.toml ./.streamlit/config.toml

# root 가 아닌 사용자로 실행한다.
RUN useradd --create-home app && chown -R app:app /app
USER app

# 호스트가 PORT 를 주면(Heroku·Render 등) 그 포트로, 아니면 8501 로 연다.
# SUPABASE_URL / SUPABASE_KEY 는 이미지에 넣지 않고 호스트의 환경 변수로 주입한다.
EXPOSE 8501
CMD ["sh", "-c", "streamlit run src/main.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
