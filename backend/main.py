from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from backend.recommend_engine import (
        df,
        search_games as engine_search_games,
        filter_games as engine_filter_games,
        recommend_games as engine_recommend_games,
    )
except ImportError:
    from recommend_engine import (
        df,
        search_games as engine_search_games,
        filter_games as engine_filter_games,
        recommend_games as engine_recommend_games,
    )

app = FastAPI(title="BoardGame Recommender API")


# POST /recommend에서 받을 JSON 요청 바디
class RecommendRequest(BaseModel):
    game_name: str
    players: int
    max_time: int


@app.get("/")
def root():
    return {
        "message": "BoardGame Recommender API",
        "total_games": len(df)
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