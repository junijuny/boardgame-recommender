# 백엔드(FastAPI) 배포용 이미지 — Google Cloud Run(Docker) 기준
# 배포 방법: docs/deploy.md
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 의존성만 먼저 설치 (코드가 바뀌어도 이 단계는 캐시 재사용)
# 의미 기반 검색(sentence-transformers)은 설치하지 않음 → 추천은 embeddings.npz 로 정상 동작
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY backend ./backend
COPY data ./data

# embeddings.npz 가 없을 때만 TF-IDF 캐시를 이미지 빌드 때 미리 생성
RUN if [ ! -f data/embeddings.npz ]; then \
      cd backend && python -c "import features; features.load_or_compute_tfidf(features.load_games())"; \
    fi

# root 가 아닌 일반 사용자로 실행
RUN useradd -m -u 1000 user && chown -R user /app
USER user

WORKDIR /app/backend
# Cloud Run은 PORT 환경변수(기본 8080)로 포트를 알려줌
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
