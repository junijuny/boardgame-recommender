import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from backend.genres import build_genres, genre_games
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
    from genres import build_genres, genre_games
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

# 장르별 대표 게임은 데이터가 바뀌지 않으므로 서버 시작 시 한 번만 계산
GENRE_LIST = build_genres(df, mechanics)

# 백엔드를 호출할 수 있는 프론트엔드 주소 목록
# 기본값은 Vite 개발 화면(5173). 배포 시 환경변수 ALLOWED_ORIGINS 에 쉼표로 구분해 지정
# 예: ALLOWED_ORIGINS=https://boardgame-recommender.vercel.app,http://localhost:5173
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# POST /recommend에서 받을 JSON 요청 바디
class RecommendRequest(BaseModel):
    game_name: str
    players: int
    max_time: int


@app.get("/")
def root():
    return {
        "message": "BoardGame Recommender API",
        "total_games": len(df),
        "signals": active_signals(),
        "semantic_search": semantic_search_available(),
    }


@app.get("/games/search")
def search_games(query: str):
    query = query.strip()
    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    results = engine_search_games(query=query, limit=10)
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

    results = engine_filter_games(players=players, max_time=max_time, limit=10)
    return results


@app.get("/genres")
def list_genres():
    return GENRE_LIST


@app.get("/genres/{key}/games")
def list_genre_games(
    key: str,
    players: int | None = None,
    max_time: int | None = None,
):
    if players is not None and players <= 0:
        raise HTTPException(status_code=400, detail="Players must be greater than 0")
    if max_time is not None and max_time <= 0:
        raise HTTPException(status_code=400, detail="Max time must be greater than 0")

    try:
        return genre_games(df, mechanics, key, players=players, max_time=max_time)
    except ValueError:
        raise HTTPException(status_code=404, detail="Genre not found")


@app.post("/recommend")
def recommend_games(request: RecommendRequest):
    try:
        results = engine_recommend_games(
            target_game_name=request.game_name,
            players=request.players,
            max_time=request.max_time,
            top_n=5
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
            raise HTTPException(status_code=404, detail="Game not found")
        raise HTTPException(status_code=400, detail=error_msg)


# /games/{bgg_id} 보다 먼저 선언해야 "semantic-search"가 게임 ID로 해석되지 않음
@app.get("/games/semantic-search")
def semantic_search(
    query: str,
    players: int | None = None,
    max_time: int | None = None,
):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    if players is not None and players <= 0:
        raise HTTPException(status_code=400, detail="Players must be greater than 0")
    if max_time is not None and max_time <= 0:
        raise HTTPException(status_code=400, detail="Max time must be greater than 0")
    if not semantic_search_available():
        raise HTTPException(status_code=503, detail="Semantic search is not available")

    return engine_semantic_search(
        query=query, players=players, max_time=max_time, limit=10
    )


# 게임 상세 정보에 담을 항목 (검색 결과보다 설명글, 최적 인원 등이 추가됨)
DETAIL_COLUMNS = [
    "BGGId", "Name", "YearPublished", "ImagePath", "Description",
    "GameWeight", "MinPlayers", "MaxPlayers", "BestPlayers",
    "ComMinPlaytime", "ComMaxPlaytime", "BayesAvgRating", "NumUserRatings",
]


@app.get("/games/{bgg_id}")
def get_game_detail(bgg_id: int):
    matches = df[df["BGGId"] == bgg_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Game not found")
    return matches[DETAIL_COLUMNS].to_dict(orient="records")[0]