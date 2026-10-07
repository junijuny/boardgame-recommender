from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()

# clean_games.csv 경로
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "clean_games.csv"

# 정제된 CSV 데이터 불러오기
df = pd.read_csv(DATA_PATH)

# Description 결측치 처리
df["Description"] = df["Description"].fillna("")

# TF-IDF 모델 생성
tfidf = TfidfVectorizer(
    stop_words="english",
    max_features=5000
)

# 모든 게임의 Description을 TF-IDF 벡터로 변환
tfidf_matrix = tfidf.fit_transform(df["Description"])


# POST /recommend에서 받을 JSON 형식
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

    results = df[
        df["Name"].str.contains(
            query,
            case=False,
            na=False,
            regex=False
        )
    ]

    return results[
        [
            "BGGId",
            "Name",
            "YearPublished",
            "ImagePath"
        ]
    ].head(10).to_dict(orient="records")


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

    results = df[
        (df["MinPlayers"] <= players) &
        (df["MaxPlayers"] >= players) &
        (df["ComMaxPlaytime"] <= max_time) &
        (df["BayesAvgRating"] >= 5.5)
    ]

    results = results.sort_values(
        by="BayesAvgRating",
        ascending=False
    )

    return results[
        [
            "BGGId",
            "Name",
            "MinPlayers",
            "MaxPlayers",
            "ComMinPlaytime",
            "ComMaxPlaytime",
            "BayesAvgRating",
            "NumUserRatings",
            "ImagePath"
        ]
    ].head(10).to_dict(orient="records")


@app.post("/recommend")
def recommend_games(request: RecommendRequest):

    game_name = request.game_name.strip()
    players = request.players
    max_time = request.max_time

    # 입력값 검사
    if not game_name:
        raise HTTPException(
            status_code=400,
            detail="Game name cannot be empty"
        )

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

    # 1. 기준 게임 찾기
    game_matches = df[
        df["Name"].str.lower() == game_name.lower()
    ]

    if game_matches.empty:
        raise HTTPException(
            status_code=404,
            detail="Game not found"
        )

    game_index = game_matches.index[0]

    # 2. 조건에 맞는 후보 게임 필터링
    candidates = df[
        (df["MinPlayers"] <= players) &
        (df["MaxPlayers"] >= players) &
        (df["ComMaxPlaytime"] <= max_time) &
        (df["BayesAvgRating"] >= 5.5)
    ].copy()

    # 기준 게임 자체 제외
    candidates = candidates[
        candidates.index != game_index
    ]

    if candidates.empty:
        raise HTTPException(
            status_code=404,
            detail="No games match the selected conditions"
        )

    # 3. 기준 게임과 후보 게임의 코사인 유사도 계산
    similarities = cosine_similarity(
        tfidf_matrix[game_index],
        tfidf_matrix[candidates.index]
    ).flatten()

    # 4. 유사도 저장
    candidates["Similarity"] = similarities

    # 5. 유사도 우선, 평점 보조 기준으로 정렬
    candidates = candidates.sort_values(
        by=["Similarity", "BayesAvgRating"],
        ascending=[False, False]
    )

    # 6. 상위 5개 추천 결과 반환
    return candidates[
        [
            "BGGId",
            "Name",
            "YearPublished",
            "MinPlayers",
            "MaxPlayers",
            "ComMinPlaytime",
            "ComMaxPlaytime",
            "BayesAvgRating",
            "NumUserRatings",
            "ImagePath",
            "Similarity"
        ]
    ].head(5).to_dict(orient="records")