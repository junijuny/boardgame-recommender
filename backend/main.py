
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from backend import gemini
    from backend.explain import explain_games
    from backend.genres import build_genres, genre_games
    from backend.limits import RateLimiter, client_ip
    from backend.natural_search import natural_search, natural_search_available
    from backend.recommend_engine import (
        active_signals,
        df,
        mechanics,
        semantic_search_available,
    )
    from backend.recommend_engine import (
        filter_games as engine_filter_games,
    )
    from backend.recommend_engine import (
        recommend_games as engine_recommend_games,
    )
    from backend.recommend_engine import (
        search_games as engine_search_games,
    )
    from backend.recommend_engine import (
        semantic_search as engine_semantic_search,
    )
except ImportError:
    import gemini
    from explain import explain_games
    from genres import build_genres, genre_games
    from limits import RateLimiter, client_ip
    from natural_search import natural_search, natural_search_available
    from recommend_engine import (
        active_signals,
        df,
        mechanics,
        semantic_search_available,
    )
    from recommend_engine import (
        filter_games as engine_filter_games,
    )
    from recommend_engine import (
        recommend_games as engine_recommend_games,
    )
    from recommend_engine import (
        search_games as engine_search_games,
    )
    from recommend_engine import (
        semantic_search as engine_semantic_search,
    )

app = FastAPI(title="BoardGame Recommender API")

# 장르별 대표 게임은 서버 시작 시 한 번만 계산
GENRE_LIST = build_genres(df, mechanics)

# 프론트엔드 접근 허용 주소
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get(
        "ALLOWED_ORIGINS", DEFAULT_ORIGINS
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# POST /recommend 요청 데이터
class RecommendRequest(BaseModel):
    game_name: str
    players: int
    max_time: int

    # 새 기능: 이전에 추천한 게임 ID 목록
    # 전달하지 않으면 기존 추천 방식 그대로 동작
    exclude_ids: list[int] = Field(default_factory=list)


# POST /search/natural 요청 데이터
class NaturalSearchRequest(BaseModel):
    query: str
    players: int
    max_time: int
    exclude_ids: list[int] = Field(default_factory=list)


MAX_NATURAL_QUERY_LENGTH = 300

# 테스트에서 교체할 수 있도록 모듈 전역으로 둔다
natural_limiter = RateLimiter(10, 60)


# POST /explain 요청 데이터
class ExplainRequest(BaseModel):
    mode: Literal["similar", "query"]
    basis: str
    game_ids: list[int]


MAX_EXPLAIN_BASIS_LENGTH = 300
MAX_EXPLAIN_GAMES = 10

explain_limiter = RateLimiter(30, 60)


@app.get("/")
def root():
    return {
        "message": "BoardGame Recommender API",
        "total_games": len(df),
        "signals": active_signals(),
        "semantic_search": semantic_search_available(),
        "natural_search": natural_search_available(),
        "explanations": gemini.get_client() is not None,
    }


@app.get("/games/search")
def search_games(query: str):
    query = query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    # 기존 게임 검색 기능 유지
    results = engine_search_games(query, limit=10)
    return results


@app.get("/games/filter")
def filter_games(players: int, max_time: int):
    if players <= 0:
        raise HTTPException(
            status_code=400,
            detail="Players must be greater than 0"
        )

    if max_time <= 0:
        raise HTTPException(
            status_code=400,
            detail="Max time must be greater than 0"
        )

    results = engine_filter_games(
        players=players,
        max_time=max_time,
        limit=10,
    )
    return results


@app.get("/genres")
def list_genres():
    return GENRE_LIST


@app.get("/genres/{key}/games")
def list_genre_games(
    key: str,
    players: int | None = None,
    max_time: int | None = None,
    # 이미 보여 준 게임 Id. 주소에 ?exclude_ids=13&exclude_ids=822처럼 여러 번 붙여서 보냄
    exclude_ids: list[int] = Query(default=[]),
):
    if players is not None and players <= 0:
        raise HTTPException(
            status_code=400,
            detail="Players must be greater than 0"
        )

    if max_time is not None and max_time <= 0:
        raise HTTPException(
            status_code=400,
            detail="Max time must be greater than 0"
        )

    try:
        return genre_games(
            df,
            mechanics,
            key,
            players=players,
            max_time=max_time,
            exclude_ids=exclude_ids,
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Genre not found"
        )


@app.post("/recommend")
def recommend_games(request: RecommendRequest):
    try:
        results = engine_recommend_games(
            target_game_name=request.game_name,
            players=request.players,
            max_time=request.max_time,
            top_n=5,
            exclude_ids=request.exclude_ids,
        )

        if not results:
            raise HTTPException(
                status_code=404,
                detail="No games match the selected conditions"
            )

        return results

    except ValueError as e:
        error_msg = str(e)

        if "Game not found" in error_msg:
            raise HTTPException(
                status_code=404,
                detail="Game not found"
            )

        raise HTTPException(
            status_code=400,
            detail=error_msg
        )


@app.post("/search/natural")
def search_natural(body: NaturalSearchRequest, request: Request):
    query = body.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    if len(query) > MAX_NATURAL_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail="Search query is too long"
        )

    if body.players <= 0:
        raise HTTPException(
            status_code=400,
            detail="Players must be greater than 0"
        )

    if body.max_time <= 0:
        raise HTTPException(
            status_code=400,
            detail="Max time must be greater than 0"
        )

    if not natural_search_available():
        raise HTTPException(
            status_code=503,
            detail="Natural language search is not available"
        )

    if not natural_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many requests"
        )

    try:
        results = natural_search(
            query,
            players=body.players,
            max_time=body.max_time,
            exclude_ids=body.exclude_ids,
            top_n=5,
        )
    except gemini.GeminiError:
        raise HTTPException(
            status_code=503,
            detail="Natural language search is temporarily unavailable"
        )

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No games match the selected conditions"
        )

    return results


@app.post("/explain")
def explain(body: ExplainRequest, request: Request):
    basis = body.basis.strip()

    if not basis:
        raise HTTPException(
            status_code=400,
            detail="Basis cannot be empty"
        )

    if len(basis) > MAX_EXPLAIN_BASIS_LENGTH:
        raise HTTPException(
            status_code=400,
            detail="Basis is too long"
        )

    if not body.game_ids or len(body.game_ids) > MAX_EXPLAIN_GAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Provide between 1 and {MAX_EXPLAIN_GAMES} game ids"
        )

    if gemini.get_client() is None:
        raise HTTPException(
            status_code=503,
            detail="Explanations are not available"
        )

    if not explain_limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many requests"
        )

    try:
        reasons = explain_games(body.mode, basis, body.game_ids)
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Game not found"
        )
    except gemini.GeminiError:
        raise HTTPException(
            status_code=503,
            detail="Explanations are temporarily unavailable"
        )

    return {"reasons": {str(k): v for k, v in reasons.items()}}


# /games/{bgg_id}보다 먼저 선언해야 함
@app.get("/games/semantic-search")
def semantic_search(
    query: str,
    players: int | None = None,
    max_time: int | None = None,
):
    query = query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    if players is not None and players <= 0:
        raise HTTPException(
            status_code=400,
            detail="Players must be greater than 0"
        )

    if max_time is not None and max_time <= 0:
        raise HTTPException(
            status_code=400,
            detail="Max time must be greater than 0"
        )

    if not semantic_search_available():
        raise HTTPException(
            status_code=503,
            detail="Semantic search is not available"
        )

    return engine_semantic_search(
        query=query,
        players=players,
        max_time=max_time,
        limit=10,
    )


# 게임 상세 정보에 포함할 항목
DETAIL_COLUMNS = [
    "BGGId",
    "Name",
    "YearPublished",
    "ImagePath",
    "Description",
    "GameWeight",
    "MinPlayers",
    "MaxPlayers",
    "BestPlayers",
    "ComMinPlaytime",
    "ComMaxPlaytime",
    "BayesAvgRating",
    "NumUserRatings",
]


@app.get("/games/{bgg_id}")
def get_game_detail(bgg_id: int):
    matches = df[df["BGGId"] == bgg_id]

    if matches.empty:
        raise HTTPException(
            status_code=404,
            detail="Game not found"
        )

    return matches[DETAIL_COLUMNS].to_dict(
        orient="records"
    )[0]
