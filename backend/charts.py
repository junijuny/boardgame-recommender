"""
backend/charts.py
인기 차트 만들기 (GET /charts, GET /charts/{key})

보드게임을 잘 몰라서 고를 게임도, 장르도 없는 사용자에게 처음 보여 줄 목록.
(추천 시스템에서 정보가 없는 신규 사용자에게 인기 기반 추천을 먼저 보여 주는 방식)

차트 4개
- top         : BGG 전체 순위(Rank:boardgame) 높은 순
- most_owned  : 게임을 가진 사람 수(NumOwned) 많은 순
- most_wanted : 위시리스트에 넣은 사람 수(NumWish) 많은 순
- new         : 데이터에서 가장 최근 3년(2019~2021년) 출시작 중 평점 높은 순 (리뷰 1,000개 이상)

데이터는 2021년에 찍어 둔 BGG 스냅샷이라 "요즘 뜨는 게임"이 아니라 "데이터셋 기준 인기 순위"다.
순위·보유 수·위시 수는 games.csv 에만 있어서, 서버 시작을 느리게 하지 않도록
처음 차트를 요청할 때 한 번만 읽고 결과를 기억해 둔다 (main.py).
"""

from pathlib import Path
from typing import Any

import pandas as pd

try:
    from backend.features import RAW_GAMES_PATH
    from backend.genres import GENRE_GAME_COLUMNS
except ImportError:
    from features import RAW_GAMES_PATH
    from genres import GENRE_GAME_COLUMNS

# 화면에 보여줄 순서대로 정리한 차트 목록 (화면이 영어라 label, description도 영어)
CHARTS = [
    {"key": "top", "label": "Top Ranked", "description": "Highest overall BoardGameGeek rank"},
    {"key": "most_owned", "label": "Most Owned", "description": "Games the most people own"},
    {"key": "most_wanted", "label": "Most Wanted", "description": "Most added to wishlists"},
    {"key": "new", "label": "New & Popular", "description": "Top rated recent releases"},
]
CHART_KEYS = [chart["key"] for chart in CHARTS]

# 차트 게임마다 돌려줄 필드 (장르 게임 필드 + 차트 숫자)
CHART_GAME_COLUMNS = [*GENRE_GAME_COLUMNS, "BggRank", "NumOwned", "NumWish", "NumUserRatings"]

NEW_RELEASE_YEARS = 3  # 신작 차트: 데이터의 가장 최근 연도부터 몇 년치를 신작으로 볼지


def load_chart_stats(df: pd.DataFrame, path: Path = RAW_GAMES_PATH) -> pd.DataFrame:
    """games.csv 에서 순위·보유 수·위시 수를 읽어 df 와 같은 행 순서로 붙인 표를 반환"""
    raw = pd.read_csv(path, usecols=["BGGId", "Rank:boardgame", "NumOwned", "NumWish"])
    stats = df[["BGGId"]].merge(raw, on="BGGId", how="left")
    # 값이 없으면 NaN 이 되어 JSON 변환이 실패(500)하므로 숫자로 채운다
    # 순위가 없는 게임은 가장 뒤 순위보다 큰 값으로 두어 top 차트에 나오지 않게 한다
    worst_rank = stats["Rank:boardgame"].max()
    stats["BggRank"] = stats["Rank:boardgame"].fillna(worst_rank + 1).astype(int)
    stats["NumOwned"] = stats["NumOwned"].fillna(0).astype(int)
    stats["NumWish"] = stats["NumWish"].fillna(0).astype(int)
    return stats[["BggRank", "NumOwned", "NumWish"]]


def chart_games(
    df: pd.DataFrame,
    stats: pd.DataFrame,
    key: str,
    limit: int = 10,
    min_ratings: int = 1000,
) -> list[dict[str, Any]]:
    """차트 key 의 게임 limit 개를 순위대로 반환 (모르는 key 면 ValueError)"""
    if key not in CHART_KEYS:
        raise ValueError(f"Unknown chart: {key}")

    games = pd.concat([df.reset_index(drop=True), stats.reset_index(drop=True)], axis=1)
    if key == "top":
        picked = games.sort_values(["BggRank", "NumUserRatings"], ascending=[True, False])
    elif key == "most_owned":
        picked = games.sort_values(["NumOwned", "BayesAvgRating"], ascending=[False, False])
    elif key == "most_wanted":
        picked = games.sort_values(["NumWish", "BayesAvgRating"], ascending=[False, False])
    else:  # new
        newest_year = int(games["YearPublished"].max())
        recent = games["YearPublished"] > newest_year - NEW_RELEASE_YEARS
        popular = games["NumUserRatings"] >= min_ratings
        picked = games[recent & popular].sort_values("BayesAvgRating", ascending=False)

    return picked.head(limit)[CHART_GAME_COLUMNS].to_dict(orient="records")


def build_charts(df: pd.DataFrame, stats: pd.DataFrame, limit: int = 10) -> list[dict[str, Any]]:
    """차트 4개와 차트마다 게임 limit 개를 담아 반환"""
    return [{**chart, "games": chart_games(df, stats, chart["key"], limit=limit)} for chart in CHARTS]
