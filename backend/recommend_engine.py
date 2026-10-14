"""
backend/recommend_engine.py
보드게임 조건 필터링 + TF-IDF 코사인 유사도 통합 추천 엔진 모듈
(TF-IDF 모델 및 희소 행렬 디스크 캐싱 적용)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 1. 파일 및 데이터 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "clean_games.csv"
CACHE_PATH = BASE_DIR / "data" / "tfidf_cache.joblib"

# 2. 데이터셋 로드 및 전처리
df = pd.read_csv(DATA_PATH)
df["Description"] = df["Description"].fillna("")


# 3. TF-IDF 모델 및 행렬 로드 (디스크 캐시 우선 활용 -> 0.05초 초고속 로딩)
def _load_or_compute_tfidf():
    use_cache = False
    if CACHE_PATH.exists():
        try:
            cache_mtime = CACHE_PATH.stat().st_mtime
            data_mtime = DATA_PATH.stat().st_mtime
            # 캐시가 CSV 데이터보다 최신일 때만 재사용
            if cache_mtime >= data_mtime:
                cached_data = joblib.load(CACHE_PATH)
                vectorizer = cached_data["tfidf"]
                matrix = cached_data["tfidf_matrix"]
                use_cache = True
                return vectorizer, matrix
        except Exception:
            use_cache = False

    if not use_cache:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=3000
        )
        matrix = vectorizer.fit_transform(df["Description"])
        try:
            joblib.dump({"tfidf": vectorizer, "tfidf_matrix": matrix}, CACHE_PATH)
        except Exception:
            pass
        return vectorizer, matrix


tfidf, tfidf_matrix = _load_or_compute_tfidf()

# 반환할 기본 필드 목록
DEFAULT_COLUMNS = [
    "BGGId",
    "Name",
    "YearPublished",
    "GameWeight",
    "MinPlayers",
    "MaxPlayers",
    "ComMinPlaytime",
    "ComMaxPlaytime",
    "BayesAvgRating",
    "NumUserRatings",
    "ImagePath"
]


def get_game_by_name(game_name: str) -> Optional[pd.Series]:
    """게임 이름으로 일치하는 데이터 조회 (대소문자 무시)"""
    matches = df[df["Name"].str.strip().str.lower() == game_name.strip().lower()]
    if matches.empty:
        return None
    return matches.iloc[0]


def search_games(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """게임 이름 부분 검색 (자동완성 및 검색용)"""
    query = query.strip()
    if not query:
        return []

    results = df[
        df["Name"].str.contains(
            query,
            case=False,
            na=False,
            regex=False
        )
    ]
    return results[
        ["BGGId", "Name", "YearPublished", "ImagePath"]
    ].head(limit).to_dict(orient="records")


def filter_games(
    players: int,
    max_time: int,
    min_rating: float = 5.5,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """조건(인원수, 최대 시간, 최소 평점)에 따른 게임 필터링"""
    results = df[
        (df["MinPlayers"] <= players) &
        (df["MaxPlayers"] >= players) &
        (df["ComMaxPlaytime"] <= max_time) &
        (df["BayesAvgRating"] >= min_rating)
    ].sort_values(by="BayesAvgRating", ascending=False)

    return results[DEFAULT_COLUMNS].head(limit).to_dict(orient="records")


def recommend_games(
    target_game_name: str,
    players: int,
    max_time: int,
    top_n: int = 5,
    min_rating: float = 5.5
) -> List[Dict[str, Any]]:
    """
    4주차 파이프라인: 규칙 필터링 + 코사인 유사도 결합 추천 함수
    
    Args:
        target_game_name: 기준 게임 이름 (예: 'Catan', 'Splendor')
        players: 플레이할 인원수 (1 이상)
        max_time: 최대 허용 플레이 시간(분) (1 이상)
        top_n: 반환할 추천 결과 개수 (기본 5)
        min_rating: 필터링할 최소 베이지안 평균 평점 (기본 5.5)

    Returns:
        유사도 및 게임 정보가 포함된 딕셔너리 리스트
    """
    target_game_name = target_game_name.strip()
    if not target_game_name:
        raise ValueError("Game name cannot be empty")
    if players <= 0:
        raise ValueError("Players must be greater than 0")
    if max_time <= 0:
        raise ValueError("Max time must be greater than 0")

    # 1. 기준 게임 인덱스 조회
    target_game = get_game_by_name(target_game_name)
    if target_game is None:
        raise ValueError(f"Game not found: {target_game_name}")

    target_idx = target_game.name

    # 2. 1차 하드 필터링 + 3차 평점 보정 + 기준 게임(자기 자신) 제외
    candidates = df[
        (df["MinPlayers"] <= players) &
        (df["MaxPlayers"] >= players) &
        (df["ComMaxPlaytime"] <= max_time) &
        (df["BayesAvgRating"] >= min_rating) &
        (df.index != target_idx)
    ].copy()

    if candidates.empty:
        return []

    # 3. 2차 유사도 랭킹 (필터링된 후보군에 대해서만 코사인 유사도 계산)
    target_vector = tfidf_matrix[target_idx]
    candidate_vectors = tfidf_matrix[candidates.index]

    similarities = cosine_similarity(target_vector, candidate_vectors).flatten()
    candidates["Similarity"] = similarities

    # 4. 정렬 (1순위: Similarity 내림차순, 2순위: BayesAvgRating 내림차순)
    sorted_candidates = candidates.sort_values(
        by=["Similarity", "BayesAvgRating"],
        ascending=[False, False]
    )

    # 5. 최종 반환 필드 구성
    output_columns = DEFAULT_COLUMNS + ["Similarity"]
    return sorted_candidates[output_columns].head(top_n).to_dict(orient="records")


if __name__ == "__main__":
    import sys
    import time
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # 테스트 실행
    print("=" * 60)
    print("추천 엔진 테스트 실행")
    print(f"전체 게임 수: {len(df)}")
    print(f"TF-IDF 행렬 크기: {tfidf_matrix.shape}")
    print(f"캐시 파일 위치: {CACHE_PATH} (존재 여부: {CACHE_PATH.exists()})")
    print("=" * 60)

    start_time = time.time()
    test_name = "Catan"
    test_p = 4
    test_t = 90
    print(f"테스트 입력: 기준게임='{test_name}', 인원={test_p}명, 최대시간={test_t}분")

    try:
        recs = recommend_games(test_name, test_p, test_t, top_n=5)
        elapsed = time.time() - start_time
        print(f"\n[추천 결과 Top {len(recs)}] (연산 소요 시간: {elapsed:.4f}초)")
        for i, r in enumerate(recs, 1):
            print(f"{i}위: {r['Name']} (연도: {r['YearPublished']}) | 유사도: {r['Similarity']:.4f} | 평점: {r['BayesAvgRating']:.2f} | 난이도: {r['GameWeight']:.2f}")
    except Exception as e:
        print("오류 발생:", e)
