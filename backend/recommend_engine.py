"""
backend/recommend_engine.py
보드게임 조건 필터링 + 하이브리드 유사도 추천 엔진

추천 파이프라인
1. 하드 필터링: 인원수, 최대 플레이 시간, 최소 평점
2. 유사도: 아래 신호를 가중 평균 (데이터가 없는 신호는 빼고 나머지로 다시 정규화)
   - mechanics : 메커니즘 (IDF 가중 코사인)              ← 1단계
   - themes    : 테마 (IDF 가중 코사인)                    ← 1단계
   - category  : Cat:* 카테고리 + 난이도 차이              ← 1단계
   - embedding : 문장 임베딩 코사인 (없으면 tfidf로 대체)  ← 2단계
   - cf        : 협업 필터링 (평점 데이터로 학습, 선택)    ← 3단계
3. 최종 점수: 유사도 + 평점 보정 - 같은 시리즈(변형판) 감점
4. 다양성 재정렬(MMR): 서로 너무 비슷한 게임이 Top N을 채우지 않게 함
"""

from typing import Any

import numpy as np
import pandas as pd

try:
    from backend import features, semantic
except ImportError:
    import features
    import semantic

# ---------------------------------------------------------------------------
# 데이터와 특징 행렬 로드 (서버 시작 시 1회)
# ---------------------------------------------------------------------------
df = features.load_games()
mechanics = features.load_binary_features(features.MECHANICS_PATH, df["BGGId"])
themes = features.load_binary_features(features.THEMES_PATH, df["BGGId"])
category_matrix = features.build_category_matrix(df)
tfidf, tfidf_matrix = features.load_or_compute_tfidf(df)
embeddings = features.load_embeddings(df["BGGId"])  # 없으면 None
cf = features.load_cf(df["BGGId"])                  # 없으면 None

_has_mechanics = np.diff(mechanics.binary.indptr) > 0
_has_themes = np.diff(themes.binary.indptr) > 0
_weights = df["GameWeight"].to_numpy(dtype=np.float32)
_ratings = df["BayesAvgRating"].to_numpy(dtype=np.float32)
_names_lower = df["Name"].str.strip().str.lower()

# ---------------------------------------------------------------------------
# 가중치 설정
# ---------------------------------------------------------------------------
SIGNAL_WEIGHTS = {
    "mechanics": 0.40,
    "themes": 0.15,
    "category": 0.10,
    "text": 0.20,   # embedding 이 있으면 embedding, 없으면 tfidf 사용
    "cf": 0.40,     # cf_factors.npz 가 있을 때만 사용
}
# 가중치는 backend/evaluate.py 로 튜닝함 (튜닝 표본 seed=1, 보고 표본 seed=0 분리).
# 평점 비중을 올리면 적중률은 오르지만 인기 게임 쏠림(Coverage 감소)이 생겨 0.25로 절충
RATING_WEIGHT = 0.25     # 최종 점수에서 평점이 차지하는 비중
RATING_FLOOR, RATING_CEIL = 5.5, 8.0  # 이 구간의 평점을 0~1로 환산
VARIANT_PENALTY = 0.20   # 기준 게임과 같은 시리즈/변형판 감점 (예: Catan → Simply Catan)
MMR_POOL = 50            # 다양성 재정렬 대상 후보 수
DIVERSITY = 0.15         # 이미 고른 게임과 비슷할수록 감점하는 강도

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
    "ImagePath",
]


def default_weights() -> dict[str, float]:
    """현재 준비된 데이터에 맞춘 신호별 가중치"""
    weights = {k: SIGNAL_WEIGHTS[k] for k in ("mechanics", "themes", "category")}
    weights["embedding" if embeddings is not None else "tfidf"] = SIGNAL_WEIGHTS["text"]
    if cf is not None:
        weights["cf"] = SIGNAL_WEIGHTS["cf"]
    return weights


def active_signals() -> list[str]:
    return list(default_weights())


# ---------------------------------------------------------------------------
# 유사도 계산
# ---------------------------------------------------------------------------
def _sparse_cosine(matrix, target_idx: int, cand_idx: np.ndarray) -> np.ndarray:
    return np.asarray(matrix[cand_idx] @ matrix[target_idx].T.toarray()).ravel()


def signal_similarities(
    target_idx: int, cand_idx: np.ndarray, signals: list[str]
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """신호별 (유사도 0~1, 반영 비율 0~1) 반환. 반영 비율 0 = 데이터가 없어 판단 불가"""
    n = len(cand_idx)
    ones = np.ones(n, dtype=np.float32)
    result = {}

    if "mechanics" in signals and _has_mechanics[target_idx]:
        result["mechanics"] = (
            _sparse_cosine(mechanics.weighted, target_idx, cand_idx),
            _has_mechanics[cand_idx].astype(np.float32),
        )
    if "themes" in signals and _has_themes[target_idx]:
        result["themes"] = (
            _sparse_cosine(themes.weighted, target_idx, cand_idx),
            _has_themes[cand_idx].astype(np.float32),
        )
    if "category" in signals:
        cat_sim = category_matrix[cand_idx] @ category_matrix[target_idx]
        w_t, w_c = _weights[target_idx], _weights[cand_idx]
        # 난이도 1~5. 값이 0이면 정보 없음으로 보고 중간값 0.5
        weight_sim = np.where(
            (w_t > 0) & (w_c > 0), 1.0 - np.abs(w_c - w_t) / 4.0, 0.5
        )
        result["category"] = (0.5 * cat_sim + 0.5 * weight_sim, ones)
    if "tfidf" in signals:
        result["tfidf"] = (_sparse_cosine(tfidf_matrix, target_idx, cand_idx), ones)
    if "embedding" in signals and embeddings is not None and embeddings.present[target_idx]:
        raw = embeddings.vectors[cand_idx] @ embeddings.vectors[target_idx]
        result["embedding"] = (
            embeddings.rescale(raw),
            embeddings.present[cand_idx].astype(np.float32),
        )
    if "cf" in signals and cf is not None and cf.confidence[target_idx] > 0:
        raw = cf.factors[cand_idx] @ cf.factors[target_idx]
        result["cf"] = (
            np.clip(raw, 0.0, 1.0),
            cf.confidence[target_idx] * cf.confidence[cand_idx],
        )
    return result


def hybrid_similarity(
    target_idx: int,
    cand_idx: np.ndarray,
    weights: dict[str, float] | None = None,
) -> np.ndarray:
    """신호별 유사도를 가중 평균.
    - 기준 게임에 데이터가 없는 신호는 제외 (모든 후보에 똑같이 적용되므로 공정)
    - 후보 게임에 데이터가 없으면 그 신호 값을 '평균적인 후보'(중앙값)로 채움.
      빼고 다시 정규화하면 정보가 적은 게임이 오히려 높은 점수를 받기 때문."""
    weights = weights or default_weights()
    sims = signal_similarities(target_idx, cand_idx, list(weights))
    total = np.zeros(len(cand_idx), dtype=np.float64)
    weight_sum = 0.0
    for name, (sim, coverage) in sims.items():
        known = coverage > 0
        if not known.any():
            continue
        typical = float(np.median(sim[known]))
        filled = coverage * sim + (1.0 - coverage) * typical
        total += weights[name] * filled
        weight_sum += weights[name]
    return total / weight_sum if weight_sum > 0 else total


def rating_score(cand_idx: np.ndarray) -> np.ndarray:
    return np.clip(
        (_ratings[cand_idx] - RATING_FLOOR) / (RATING_CEIL - RATING_FLOOR), 0.0, 1.0
    )


def variant_mask(target_idx: int, cand_idx: np.ndarray) -> np.ndarray:
    """기준 게임과 같은 Family 이거나 이름에 기준 게임 이름이 들어간 게임"""
    family = df.at[target_idx, "Family"]
    same_family = (df["Family"].to_numpy()[cand_idx] == family) if family else False
    name = _names_lower.iat[target_idx]
    if len(name) >= 4:
        contains = _names_lower.iloc[cand_idx].str.contains(name, regex=False).to_numpy()
    else:
        contains = np.zeros(len(cand_idx), dtype=bool)
    return np.asarray(same_family | contains, dtype=bool)


def score_candidates(
    target_idx: int,
    cand_idx: np.ndarray,
    weights: dict[str, float] | None = None,
    rating_weight: float = RATING_WEIGHT,
    variant_penalty: float = VARIANT_PENALTY,
) -> tuple[np.ndarray, np.ndarray]:
    """(유사도, 최종 점수) 반환"""
    similarity = hybrid_similarity(target_idx, cand_idx, weights)
    score = (1 - rating_weight) * similarity + rating_weight * rating_score(cand_idx)
    score = score - variant_penalty * variant_mask(target_idx, cand_idx)
    return similarity, score


def diversify(
    cand_idx: np.ndarray,
    score: np.ndarray,
    top_n: int,
    diversity: float = DIVERSITY,
) -> np.ndarray:
    """MMR: 점수가 높으면서 이미 고른 게임과 덜 비슷한 게임을 차례로 선택.
    반환값은 cand_idx 안에서의 위치 배열."""
    pool = np.argsort(-score, kind="stable")[:MMR_POOL]
    if diversity <= 0 or len(pool) <= 1:
        return pool[:top_n]

    games = cand_idx[pool]
    item_sim = (
        0.7 * (mechanics.weighted[games] @ mechanics.weighted[games].T).toarray()
        + 0.3 * (themes.weighted[games] @ themes.weighted[games].T).toarray()
    )
    family = df["Family"].to_numpy()[games]
    same_family = (family[:, None] == family[None, :]) & (family[:, None] != "")
    item_sim = np.maximum(item_sim, same_family.astype(float))

    pool_score = score[pool]
    selected: list[int] = []
    max_sim = np.zeros(len(pool))
    remaining = np.ones(len(pool), dtype=bool)
    for _ in range(min(top_n, len(pool))):
        value = np.where(remaining, pool_score - diversity * max_sim, -np.inf)
        best = int(np.argmax(value))
        selected.append(best)
        remaining[best] = False
        max_sim = np.maximum(max_sim, item_sim[best])
    return pool[selected]


# ---------------------------------------------------------------------------
# 공개 함수 (API에서 사용)
# ---------------------------------------------------------------------------
def get_game_by_name(game_name: str) -> pd.Series | None:
    """게임 이름으로 일치하는 데이터 조회 (대소문자 무시)"""
    matches = df[_names_lower == game_name.strip().lower()]
    if matches.empty:
        return None
    return matches.iloc[0]


def search_games(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """게임 이름 부분 검색 (자동완성 및 검색용)

    1) 이름이 검색어와 정확히 같은 게임 2) 이름이 검색어로 시작하는 게임
    3) 이름 중간에 검색어가 들어간 게임 순으로, 같은 순위 안에서는 리뷰 수가 많은 순으로 정렬"""
    query = query.strip()
    if not query:
        return []

    q = query.lower()
    # 순위: 0 정확히 같음, 1 검색어로 시작, 2 중간에 포함, 3 해당 없음
    exact = (_names_lower == q).to_numpy(dtype=bool, na_value=False)
    prefix = _names_lower.str.startswith(q).to_numpy(dtype=bool, na_value=False)
    contains = _names_lower.str.contains(q, regex=False).to_numpy(dtype=bool, na_value=False)
    rank = np.select([exact, prefix, contains], [0, 1, 2], default=3)

    matched = rank < 3
    results = df[matched].assign(_rank=rank[matched]).sort_values(
        ["_rank", "NumUserRatings"], ascending=[True, False]
    )
    return results[["BGGId", "Name", "YearPublished", "ImagePath"]].head(limit).to_dict(
        orient="records"
    )


def _condition_mask(players: int, max_time: int, min_rating: float) -> pd.Series:
    return (
        (df["MinPlayers"] <= players)
        & (df["MaxPlayers"] >= players)
        & (df["ComMaxPlaytime"] <= max_time)
        & (df["BayesAvgRating"] >= min_rating)
    )


def filter_games(
    players: int, max_time: int, min_rating: float = 5.5, limit: int = 10
) -> list[dict[str, Any]]:
    """조건(인원수, 최대 시간, 최소 평점)에 따른 게임 필터링"""
    results = df[_condition_mask(players, max_time, min_rating)].sort_values(
        by="BayesAvgRating", ascending=False
    )
    return results[DEFAULT_COLUMNS].head(limit).to_dict(orient="records")


def recommend_games(
    target_game_name: str,
    players: int,
    max_time: int,
    top_n: int = 5,
    min_rating: float = 5.5,
    exclude_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    조건 필터링 + 하이브리드 유사도 + 평점 보정 + 다양성 재정렬 추천

    Returns:
        게임 정보와 Similarity(유사도 0~1), Score(최종 점수),
        SharedMechanics / SharedThemes(기준 게임과의 공통점)가 담긴 딕셔너리 리스트
    """
    target_game_name = target_game_name.strip()
    if not target_game_name:
        raise ValueError("Game name cannot be empty")
    if players <= 0:
        raise ValueError("Players must be greater than 0")
    if max_time <= 0:
        raise ValueError("Max time must be greater than 0")

    target_game = get_game_by_name(target_game_name)
    if target_game is None:
        raise ValueError(f"Game not found: {target_game_name}")
    target_idx = int(target_game.name)

    mask = _condition_mask(players, max_time, min_rating) & (df.index != target_idx)

    # 이전에 추천했던 게임은 다음 추천 후보에서 제외
    if exclude_ids:
        mask = mask & ~df["BGGId"].isin(exclude_ids)

    cand_idx = np.flatnonzero(mask.to_numpy())
    if len(cand_idx) == 0:
        return []

    similarity, score = score_candidates(target_idx, cand_idx)
    picked = diversify(cand_idx, score, top_n)

    results = []
    for pos in picked:
        idx = int(cand_idx[pos])
        record = df.loc[idx, DEFAULT_COLUMNS].to_dict()
        record["Similarity"] = float(similarity[pos])
        record["Score"] = float(score[pos])
        record["SharedMechanics"] = mechanics.shared(target_idx, idx)
        record["SharedThemes"] = themes.shared(target_idx, idx)
        results.append(record)
    return results


def semantic_search_available() -> bool:
    return embeddings is not None and semantic.is_installed()


def semantic_search(
    query: str,
    players: int | None = None,
    max_time: int | None = None,
    limit: int = 10,
    min_rating: float = 5.5,
) -> list[dict[str, Any]]:
    """자연어(한국어 포함) 설명으로 게임 검색. 예: '친구들과 가볍게 하는 협력 게임'"""
    query = query.strip()
    if not query:
        raise ValueError("Search query cannot be empty")
    if not semantic_search_available():
        raise RuntimeError("Semantic search is not available")

    mask = df["BayesAvgRating"] >= min_rating
    if players is not None:
        mask &= (df["MinPlayers"] <= players) & (df["MaxPlayers"] >= players)
    if max_time is not None:
        mask &= df["ComMaxPlaytime"] <= max_time
    mask &= pd.Series(embeddings.present)
    cand_idx = np.flatnonzero(mask.to_numpy())
    if len(cand_idx) == 0:
        return []

    raw = embeddings.vectors[cand_idx] @ semantic.encode_query(query)
    # 질의-문서 유사도는 질의마다 범위가 달라서, 후보 중 중앙값~최댓값을 0~1로 환산
    low, high = np.median(raw), raw.max()
    similarity = np.clip((raw - low) / max(high - low, 1e-6), 0.0, 1.0)
    score = (1 - RATING_WEIGHT) * similarity + RATING_WEIGHT * rating_score(cand_idx)

    order = np.argsort(-score, kind="stable")[:limit]
    results = []
    for pos in order:
        record = df.loc[int(cand_idx[pos]), DEFAULT_COLUMNS].to_dict()
        record["Similarity"] = float(similarity[pos])
        record["Score"] = float(score[pos])
        results.append(record)
    return results


if __name__ == "__main__":
    import sys
    import time

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print(f"전체 게임 수: {len(df)}")
    print(f"사용 중인 유사도 신호: {default_weights()}")
    print("=" * 60)

    for name in ["Catan", "Pandemic", "Gloomhaven"]:
        start = time.time()
        recs = recommend_games(name, players=4, max_time=120, top_n=5)
        print(f"\n[{name}] 4명 / 120분 이하 ({time.time() - start:.3f}초)")
        for i, r in enumerate(recs, 1):
            print(
                f"{i}. {r['Name']} | 점수 {r['Score']:.3f} | 유사도 {r['Similarity']:.3f}"
                f" | 평점 {r['BayesAvgRating']:.2f} | 공통: {', '.join(r['SharedMechanics'])}"
            )
