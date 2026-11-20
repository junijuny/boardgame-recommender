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

import re
from collections.abc import Sequence
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
# 게임 표·메커니즘·테마는 미리 만들어 둔 시작 캐시에서 읽는다 (없으면 CSV에서 만들고 저장)
df, mechanics, themes = features.load_startup_data()
category_matrix = features.build_category_matrix(df)
embeddings = features.load_embeddings(df["BGGId"])  # 없으면 None
cf = features.load_cf(df["BGGId"])                  # 없으면 None
# 임베딩이 있으면 운영 API에서는 TF-IDF를 쓰지 않으므로 지연 로드(evaluate.py 등 호출 시에만 로드)
if embeddings is None:
    tfidf, tfidf_matrix = features.load_or_compute_tfidf(df)
else:
    tfidf, tfidf_matrix = None, None

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


def _get_tfidf_matrix():
    global tfidf, tfidf_matrix
    if tfidf_matrix is None:
        tfidf, tfidf_matrix = features.load_or_compute_tfidf(df)
    return tfidf_matrix


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
        result["tfidf"] = (_sparse_cosine(_get_tfidf_matrix(), target_idx, cand_idx), ones)
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


_SIMILAR_GAME_PATTERNS = (
    re.compile(r"^(?:games?|board\s*games?)\s+(?:like|similar\s+to)\s+(.+?)[.!?]?$", re.IGNORECASE),
    re.compile(r"^(?:something|anything)\s+similar\s+to\s+(.+?)[.!?]?$", re.IGNORECASE),
    re.compile(r"^(.+?)(?:과|와|이랑|랑)?\s*(?:같은|비슷한|유사한)\s*(?:보드\s*)?게임[.!?]?$"),
    re.compile(r"^(.+?)(?:과|와|이랑|랑)?\s*(?:같은|비슷한)\s*거[.!?]?$"),
)

# 한국에서 자주 검색되는 대표 보드게임의 한국어 별칭 -> 데이터셋 영문명(소문자)
_KOREAN_GAME_ALIASES: dict[str, str] = {
    "카탄": "catan",
    "스플렌더": "splendor",
    "팬데믹": "pandemic",
    "카르카손": "carcassonne",
    "티켓 투 라이드": "ticket to ride",
    "티켓투라이드": "ticket to ride",
    "코드네임": "codenames",
    "딕싯": "dixit",
    "아줄": "azul",
    "도미니언": "dominion",
    "글룸헤이븐": "gloomhaven",
    "테라포밍 마스": "terraforming mars",
    "테라포밍마스": "terraforming mars",
    "윙스팬": "wingspan",
    "세븐 원더스": "7 wonders",
    "세븐원더스": "7 wonders",
    "세븐 원더스 듀얼": "7 wonders duel",
    "세븐원더스 듀얼": "7 wonders duel",
    "아그리콜라": "agricola",
    "패치워크": "patchwork",
    "할리갈리": "halli galli",
    "루미큐브": "rummikub",
    "다빈치 코드": "coda",
    "다빈치코드": "coda",
    "뱅": "bang!",
    "뱅!": "bang!",
    "시크릿 히틀러": "secret hitler",
    "레지스탕스 아발론": "the resistance: avalon",
    "아발론": "the resistance: avalon",
    "쿠": "coup",
    "러브 레터": "love letter",
    "러브레터": "love letter",
    "스시 고": "sushi go!",
    "스시고": "sushi go!",
    "킹도미노": "kingdomino",
    "캐스캐디아": "cascadia",
    "브라스 버밍엄": "brass: birmingham",
    "가이아 프로젝트": "gaia project",
    "스피릿 아일랜드": "spirit island",
    "루트": "root",
    "에버델": "everdell",
    "스컬": "skull",
    "저스트 원": "just one",
    "웨이브렝스": "wavelength",
    "자이푸르": "jaipur",
    "하나미코지": "hanamikoji",
    "하이브": "hive",
    "오니타마": "onitama",
    "좀비사이드": "zombicide",
    "데드 오브 윈터": "dead of winter: a crossroads game",
    "미스테리움": "mysterium",
    "클루": "clue",
    "모노폴리": "monopoly",
    "블로커스": "blokus",
    "보난자": "bohnanza",
    "달무티": "the great dalmuti",
    "티츄": "tichu",
    "스컬 킹": "skull king",
    "스컬킹": "skull king",
    "더 크루": "the crew: the quest for planet nine",
    "포비든 아일랜드": "forbidden island",
    "클랭크": "clank!: a deck-building adventure",
}


def _game_summary(row: pd.Series) -> dict[str, Any]:
    """GameSummary 형식의 요약 딕셔너리 생성"""
    year = row["YearPublished"]
    image = row["ImagePath"]
    return {
        "BGGId": int(row["BGGId"]),
        "Name": str(row["Name"]),
        "YearPublished": int(year) if pd.notna(year) else 0,
        "ImagePath": "" if pd.isna(image) else str(image),
    }


def _find_summary_by_name(name_lower: str) -> dict[str, Any] | None:
    """정규화된 게임 이름(한국어 별칭 포함)과 일치하는 대표 게임 요약(리뷰 수 최다 판본) 반환"""
    canonical = _KOREAN_GAME_ALIASES.get(name_lower, name_lower)
    matches = df[_names_lower == canonical]
    if matches.empty:
        return None
    best = matches.sort_values("NumUserRatings", ascending=False).iloc[0]
    return _game_summary(best)


def detect_game(query: str) -> tuple[dict[str, Any], bool] | None:
    """검색어에서 게임 이름을 감지해 (요약 정보, 명시적 유사 패턴 여부) 반환.

    - 'games like Catan' 등 명시적 유사 패턴이면 (summary, True)
    - 게임 이름이 정확히 일치하면 (summary, False)
    """
    text = query.strip()
    if not text:
        return None

    for pattern in _SIMILAR_GAME_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        candidate = match.group(1).strip().lower()
        if candidate:
            summary = _find_summary_by_name(candidate)
            if summary is not None:
                return summary, True

    summary = _find_summary_by_name(text.lower())
    if summary is not None:
        return summary, False

    return None


def exclude_mask(exclude_ids: Sequence[int] | None) -> pd.Series:
    """exclude_ids에 포함된 게임과 이름이 같은 중복 행까지 제외하는 마스크"""
    if not exclude_ids:
        return pd.Series(True, index=df.index)
    by_id = df["BGGId"].isin(exclude_ids)
    excluded_names = set(_names_lower[by_id].dropna())
    return ~(by_id | _names_lower.isin(excluded_names))


def validate_time_range(min_time: int, max_time: int | None) -> None:
    """플레이 시간 구간 검사. 잘못되면 ValueError (메시지는 API 응답에 그대로 쓴다)
    max_time이 None이면 상한 없는 구간 (예: 슬라이더의 "2 hr or more" 칸)"""
    if max_time is not None and max_time <= 0:
        raise ValueError("Max time must be greater than 0")
    if min_time < 0:
        raise ValueError("Min time must be 0 or greater")
    if max_time is not None and min_time >= max_time:
        raise ValueError("Min time must be less than max time")


def _condition_mask(
    players: int, max_time: int | None, min_rating: float, min_time: int = 0
) -> pd.Series:
    """인원·플레이 시간·평점 조건.

    플레이 시간은 게임의 최대 플레이 시간(ComMaxPlaytime)이 구간 [min_time, max_time]에 드는지 본다.
    양 끝을 모두 포함해서, 프론트엔드 슬라이더의 경계 값(30·60·90·120분) 게임은 양쪽 칸에 모두 나온다.
    예) 60분 게임은 30~60분 칸과 60~90분 칸 모두
    min_time이 0이면 예전처럼 최대 시간만 거른다. max_time이 None이면 상한 없이 min_time 이상 전체.
    플레이 시간이 0으로 기록된 게임은 항상 뺀다."""
    mask = (
        (df["MinPlayers"] <= players)
        & (df["MaxPlayers"] >= players)
        & (df["ComMaxPlaytime"] > 0)
        & (df["ComMaxPlaytime"] >= min_time)
        & (df["BayesAvgRating"] >= min_rating)
    )
    if max_time is not None:
        mask &= df["ComMaxPlaytime"] <= max_time
    return mask


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
    max_time: int | None,
    top_n: int = 5,
    min_rating: float = 5.5,
    exclude_ids: list[int] | None = None,
    min_time: int = 0,
) -> list[dict[str, Any]]:
    """
    조건 필터링 + 하이브리드 유사도 + 평점 보정 + 다양성 재정렬 추천

    플레이 시간은 양 끝을 포함한 구간 [min_time, max_time] (분). min_time을 생략하면 max_time 이하 전체,
    max_time이 None이면 min_time 이상 전체

    Returns:
        게임 정보와 Similarity(유사도 0~1), Score(최종 점수),
        SharedMechanics / SharedThemes(기준 게임과의 공통점)가 담긴 딕셔너리 리스트
    """
    target_game_name = target_game_name.strip()
    if not target_game_name:
        raise ValueError("Game name cannot be empty")
    if players <= 0:
        raise ValueError("Players must be greater than 0")
    validate_time_range(min_time, max_time)

    target_game = get_game_by_name(target_game_name)
    if target_game is None:
        raise ValueError(f"Game not found: {target_game_name}")
    target_idx = int(target_game.name)

    mask = _condition_mask(players, max_time, min_rating, min_time) & (df.index != target_idx)

    # 이전에 추천했던 게임(및 같은 이름의 중복 행)은 다음 추천 후보에서 제외
    if exclude_ids:
        mask = mask & exclude_mask(exclude_ids)

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
