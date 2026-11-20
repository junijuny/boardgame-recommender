# 백엔드(FastAPI) 배포용 이미지 — Google Cloud Run(Docker) 기준
# 배포 방법: docs/deploy.md
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 의존성만 먼저 설치 (코드가 바뀌어도 이 단계는 캐시 재사용)
# 자연어 검색·설명(Gemini)은 HTTP API(google-genai)라서 무거운 의존성이 추가되지 않음
# (data/gemini_embeddings.npz 는 아래 COPY data 로 함께 들어가고, GEMINI_API_KEY 는 배포 시 환경 변수로 전달)
# 의미 기반 검색(sentence-transformers)은 설치하지 않음 → 추천은 embeddings.npz 로 정상 동작
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY backend ./backend
COPY data ./data

# TF-IDF 캐시를 이미지 빌드 때 항상 미리 생성 (.dockerignore 가 로컬 캐시를 빼므로 여기서 새로 만들어 이미지에 남는다)
# 자연어 검색의 단어 일치(terms)가 첫 질의에서 TF-IDF 를 새로 학습하지 않게 한다
RUN cd backend && python -c "import features; features.load_or_compute_tfidf(features.load_games())"
# 게임 표·메커니즘·테마 시작 캐시도 미리 생성 → 서버가 켜질 때 CSV를 다시 읽지 않아 콜드스타트가 줄어든다
RUN cd backend && python -c "import features; features.load_startup_data()"

# root 가 아닌 일반 사용자로 실행
RUN useradd -m -u 1000 user && chown -R user /app
USER user

WORKDIR /app/backend
# Cloud Run은 PORT 환경변수(기본 8080)로 포트를 알려줌
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
