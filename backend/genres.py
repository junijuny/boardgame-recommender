"""
backend/genres.py
장르별 대표 게임 목록 만들기 (GET /genres)

- 장르 7개는 BGG 공식 카테고리(Cat:* 컬럼)를 그대로 사용
  (전략은 Cat:Strategy 와 Cat:Abstract 를 합쳐서 판정)
- 추리는 BGG 카테고리에 없어서 mechanics.csv 의 'Deduction' 메커니즘으로 판정
- 대표 게임: 리뷰가 충분히 많은 게임 중 평점(BayesAvgRating)이 높은 순
"""

from typing import Any

import numpy as np
import pandas as pd

try:
    from backend.features import BinaryFeatures
except ImportError:
    from features import BinaryFeatures

# 화면에 보여줄 순서대로 정리한 장르 목록
GENRES = [
    {"key": "strategy", "label": "전략", "description": "깊이 있는 계획과 수 싸움"},
    {"key": "family", "label": "가족", "description": "누구나 쉽게 함께"},
    {"key": "party", "label": "파티", "description": "여럿이 왁자지껄"},
    {"key": "thematic", "label": "테마", "description": "이야기와 세계관에 몰입"},
    {"key": "war", "label": "워게임", "description": "전투와 역사 시뮬레이션"},
    {"key": "childrens", "label": "어린이", "description": "아이와 함께 즐기는"},
    {"key": "cgs", "label": "카드게임", "description": "카드를 모으고 덱을 짜는"},
    {"key": "deduction", "label": "추리", "description": "단서를 모아 정답을 맞히는"},
]

# 카테고리 컬럼 하나로 판정하는 장르
GENRE_CATEGORY = {
    "family": "Cat:Family",
    "party": "Cat:Party",
    "thematic": "Cat:Thematic",
    "war": "Cat:War",
    "childrens": "Cat:Childrens",
    "cgs": "Cat:CGS",
}

# 장르 카드에 담을 게임 정보
GENRE_GAME_COLUMNS = [
    "BGGId", "Name", "YearPublished", "ImagePath", "GameWeight",
    "ComMinPlaytime", "ComMaxPlaytime", "BayesAvgRating",
]


def genre_mask(df: pd.DataFrame, mechanics: BinaryFeatures, key: str) -> np.ndarray:
    """각 게임(df의 행)이 해당 장르에 속하는지 True/False 배열로 반환"""
    if key == "strategy":
        return ((df["Cat:Strategy"] == 1) | (df["Cat:Abstract"] == 1)).to_numpy()
    if key == "deduction":
        col = list(mechanics.names).index("Deduction")
        return mechanics.binary[:, col].toarray().ravel() > 0
    if key in GENRE_CATEGORY:
        return (df[GENRE_CATEGORY[key]] == 1).to_numpy()
    raise ValueError(f"Unknown genre: {key}")


def build_genres(
    df: pd.DataFrame,
    mechanics: BinaryFeatures,
    limit: int = 6,
    min_ratings: int = 1000,
) -> list[dict[str, Any]]:
    """장르마다 리뷰 수 min_ratings 이상인 게임 중 평점 상위 limit개를 담아 반환"""
    popular = (df["NumUserRatings"] >= min_ratings).to_numpy()
    result = []
    for genre in GENRES:
        picked = df[genre_mask(df, mechanics, genre["key"]) & popular]
        top = picked.sort_values("BayesAvgRating", ascending=False).head(limit)
        result.append({**genre, "games": top[GENRE_GAME_COLUMNS].to_dict(orient="records")})
    return result



def genre_games(
    df: pd.DataFrame,
    mechanics: BinaryFeatures,
    key: str,
    players: int | None = None,
    max_time: int | None = None,
    limit: int = 6,
    min_ratings: int = 1000,
    min_rating: float = 5.5,
) -> list[dict[str, Any]]:
    """장르 + 인원/시간 조건에 맞는 게임 (players, max_time은 선택)

    리뷰 수 min_ratings 이상인 인기 게임을 먼저, 그 안에서 평점 높은 순으로 고름
    조건이 까다로워 인기 게임이 limit개보다 적으면 나머지 게임으로 채움"""
    mask = genre_mask(df, mechanics, key) & (df["BayesAvgRating"] >= min_rating).to_numpy()
    if players is not None:
        mask = mask & ((df["MinPlayers"] <= players) & (df["MaxPlayers"] >= players)).to_numpy()
    if max_time is not None:
        mask = mask & (df["ComMaxPlaytime"] <= max_time).to_numpy()

    picked = df[mask].copy()
    picked["IsPopular"] = picked["NumUserRatings"] >= min_ratings
    top = picked.sort_values(["IsPopular", "BayesAvgRating"], ascending=[False, False]).head(limit)
    return top[GENRE_GAME_COLUMNS].to_dict(orient="records")
