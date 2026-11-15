"""자연어 검색 엔진: Gemini 의도 추출 + 임베딩 유사도 + 태그 일치 + 평점."""

import re
import threading
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from backend import features, gemini, profiles, recommend_engine as eng, series
except ImportError:
    import features
    import gemini
    import profiles
    import recommend_engine as eng
    import series

MIN_RATING = 5.5
# 리뷰가 적은 무명 게임은 설명글이 짧고 일반적이라("우주를 탐험하는 게임입니다") 짧은 질의와
# 가장 가깝게 나와 대표 게임을 밀어낸다. 장르 화면과 같은 기준(리뷰 1,000개 이상)으로 후보를 제한
MIN_REVIEWS = 1000
# "가장 유명한/평점 높은/최신" 질의는 설명글 유사도가 아니라 이 열의 값 순으로 고른다
SORT_COLUMNS = {"popularity": "NumUserRatings", "rating": "BayesAvgRating", "newest": "YearPublished"}
# 순위 질의에 장르 묘사도 있으면("가장 유명한 우주 게임") 임베딩 상위 이 개수 안에서만 정렬
SORT_POOL = 50
# 유사도 = 임베딩 + 태그 일치 + 단어 일치 (없는 신호는 빼고 나머지 비중으로 다시 맞춘다)
EMBEDDING_WEIGHT = 0.7
TAG_WEIGHT = 0.15
WORD_WEIGHT = 0.15
# 최종 점수 = 유사도 + 평점 + 보조 신호(추천 인원 적합도, 언어 의존도)
SIMILARITY_WEIGHT = 0.65
RATING_WEIGHT = 0.2
SOFT_WEIGHT = 0.15
MAX_WORDS = 3
MAX_WORD_CHARS = 40
AGE_RANGE = (2.0, 18.0)
_HANGUL = re.compile("[ㄱ-ㆎ가-힣]")
CACHE_SIZE = 256
# 프로필 임베딩이 있는 게임의 유사도 = (1-w)*원문 코사인 + w*프로필 코사인 (0 = 원문만, 1 = 프로필만)
PROFILE_VECTOR_WEIGHT = 0.5
PROFILE_DOC_VERSION = 1


@dataclass
class GeminiIndex:
    vectors: np.ndarray  # float32 (len(df), dim), 없는 게임은 0 행
    present: np.ndarray  # bool (len(df),)
    profile_vectors: np.ndarray | None = None  # float32 (프로필 있는 게임 수, dim)
    profile_pos: np.ndarray | None = None  # int (len(df),), profile_vectors 의 행 번호, 없으면 -1


def _read_npz(path: Path, label: str):
    """(ids, vectors) 또는 None. 모델·차원이 다르면 None"""
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            if str(data["model_name"]) != gemini.EMBED_MODEL or int(data["dim"]) != gemini.EMBED_DIM:
                return None
            if label == "profile" and int(data["doc_version"]) != PROFILE_DOC_VERSION:
                return None
            return data["ids"], data["vectors"]
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Warning: could not load Gemini {"" if label == "document" else label + " "}embeddings from {path}: {exc}")
        return None


def _place(ids: np.ndarray, stored: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """저장된 벡터를 eng.df 행 순서로 배치 -> (present, vectors)"""
    position = pd.Series(np.arange(len(ids)), index=ids)
    rows = position.reindex(eng.df["BGGId"].to_numpy())
    present = rows.notna().to_numpy()
    vectors = np.zeros((len(eng.df), stored.shape[1]), dtype=np.float32)
    vectors[present] = stored[rows[present].astype(int).to_numpy()].astype(np.float32)
    return present, vectors


def load_index(
    path: Path = features.GEMINI_EMBEDDINGS_PATH, profile_path: Path = features.PROFILE_EMBEDDINGS_PATH
) -> GeminiIndex | None:
    base = _read_npz(path, "document")
    if base is None:
        return None
    present, vectors = _place(*base)
    index = GeminiIndex(vectors=vectors, present=present)
    prof = _read_npz(profile_path, "profile")
    if prof is not None and prof[1].shape[1] == vectors.shape[1]:
        has, pvecs = _place(*prof)
        rows = np.flatnonzero(has)
        pos = np.full(len(has), -1, dtype=np.int64)
        pos[rows] = np.arange(len(rows))
        index.profile_vectors, index.profile_pos = pvecs[rows], pos
    return index


_index: GeminiIndex | None = load_index()


def set_index(index: GeminiIndex | None) -> None:
    global _index
    _index = index


def natural_search_available() -> bool:
    return gemini.get_client() is not None and _index is not None


class _LRU:
    def __init__(self, size: int = CACHE_SIZE):
        self._size = size
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        return None

    def put(self, key, value) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_intent_cache = _LRU()
_vector_cache = _LRU()


def clear_caches() -> None:
    _intent_cache.clear()
    _vector_cache.clear()
    global _text_lower
    _text_lower = None


def _clean_tags(names, vocab: set[str], drop: set[str] = frozenset()) -> tuple[str, ...]:
    canonical = {v.lower(): v for v in vocab}
    out: list[str] = []
    for name in names:
        name = canonical.get(str(name).strip().lower())
        if name is not None and name not in drop and name not in out:
            out.append(name)
    return tuple(out)


def _clean_words(words) -> tuple[str, ...]:
    """영어 단어만 (한글 제외), 40자 이하, 대소문자 무시 중복 제거, 최대 3개"""
    out: list[str] = []
    for word in words:
        word = str(word).strip()
        if not word or len(word) > MAX_WORD_CHARS or _HANGUL.search(word):
            continue
        if word.lower() not in (w.lower() for w in out):
            out.append(word)
    return tuple(out[:MAX_WORDS])


def sanitize_intent(intent: gemini.QueryIntent, raw_query: str) -> gemini.QueryIntent:
    mech_vocab = {str(n) for n in eng.mechanics.names}
    theme_vocab = {str(n) for n in eng.themes.names}
    exclude_mechanics = _clean_tags(intent.exclude_mechanics, mech_vocab)
    exclude_themes = _clean_tags(intent.exclude_themes, theme_vocab)

    low, high = intent.weight_min, intent.weight_max
    low = None if low is None else min(max(float(low), 1.0), 5.0)
    high = None if high is None else min(max(float(high), 1.0), 5.0)
    if low is not None and high is not None and low > high:
        low, high = high, low

    sort = intent.sort if intent.sort in gemini.SORT_OPTIONS else "relevance"
    search_text = (intent.search_text or "").strip()
    # 순위 질의("가장 유명한 게임")는 장르 묘사가 없을 수 있다 → 빈 문장이면 임베딩 없이 정렬만 한다
    if not search_text and sort == "relevance":
        search_text = raw_query

    return gemini.QueryIntent(
        search_text=search_text,
        include_mechanics=_clean_tags(intent.include_mechanics, mech_vocab, set(exclude_mechanics)),
        exclude_mechanics=exclude_mechanics,
        include_themes=_clean_tags(intent.include_themes, theme_vocab, set(exclude_themes)),
        exclude_themes=exclude_themes,
        weight_min=low,
        weight_max=high,
        sort=sort,
        age_max=None if intent.age_max is None else min(max(float(intent.age_max), AGE_RANGE[0]), AGE_RANGE[1]),
        categories=_clean_tags(intent.categories, set(gemini.CATEGORY_NAMES)),
        low_text=bool(intent.low_text),
        keywords=_clean_words(intent.keywords),
        terms=_clean_words(intent.terms),
    )


def _get_intent(client, query: str) -> gemini.QueryIntent:
    key = query.strip().lower()
    cached = _intent_cache.get(key)
    if cached is not None:
        return cached
    gemini.charge()
    raw = client.extract_intent(
        query, [str(n) for n in eng.mechanics.names], [str(n) for n in eng.themes.names]
    )
    intent = sanitize_intent(raw, query)
    _intent_cache.put(key, intent)
    return intent


def _get_query_vector(client, search_text: str, dim: int) -> np.ndarray:
    cached = _vector_cache.get(search_text)
    if cached is not None:
        return cached
    gemini.charge()
    vec = np.asarray(client.embed_query(search_text), dtype=np.float32)
    if vec.shape != (dim,):
        raise gemini.GeminiError(f"Unexpected query vector shape {vec.shape}")
    _vector_cache.put(search_text, vec)
    return vec


def _tag_columns(features_, names: tuple[str, ...]) -> np.ndarray:
    lookup = {str(n): i for i, n in enumerate(features_.names)}
    return np.array([lookup[n] for n in names], dtype=int)


_text_lower: pd.Series | None = None


def _whole_word(text: pd.Series, word: str) -> np.ndarray:
    return text.str.contains(r"(?<!\w)" + re.escape(word.lower()) + r"(?!\w)", regex=True).to_numpy()


def _metadata_text(cand_idx: np.ndarray) -> pd.Series:
    """후보마다 프로필의 franchise, designers, designer_countries 를 이어 붙인 소문자 문자열"""
    ids = eng.df["BGGId"].to_numpy()[cand_idx]
    rows = []
    for bgg_id in ids:
        p = profiles.PROFILES.get(int(bgg_id), {})
        rows.append(" | ".join(
            str(v) for key in ("franchise", "designers", "designer_countries") for v in p.get(key) or ()
        ).lower())
    return pd.Series(rows, dtype=object)


def keyword_matches(cand_idx: np.ndarray, keywords: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """(이름+설명 일치, 프로필 메타데이터 일치) 후보 x 키워드 bool 행렬. 모두 통단어, 대소문자 무시"""
    global _text_lower
    if _text_lower is None:
        _text_lower = (eng.df["Name"].fillna("") + " " + eng.df["Description"]).str.lower()
    text = _text_lower.iloc[cand_idx]
    meta_text = _metadata_text(cand_idx)
    text_hit = np.zeros((len(cand_idx), len(keywords)), dtype=bool)
    meta_hit = np.zeros_like(text_hit)
    for j, word in enumerate(keywords):
        text_hit[:, j] = _whole_word(text, word)
        meta_hit[:, j] = _whole_word(meta_text, word)
    return text_hit, meta_hit


def keyword_hits(cand_idx: np.ndarray, keywords: tuple[str, ...]) -> np.ndarray:
    """후보 x 키워드 bool 행렬: 이름+설명 또는 프로필 메타데이터에 키워드가 통단어로 들어 있는가"""
    text_hit, meta_hit = keyword_matches(cand_idx, keywords)
    return text_hit | meta_hit


def _word_score(cand_idx: np.ndarray, terms: tuple[str, ...]) -> np.ndarray | None:
    """설명글 TF-IDF 와 terms 의 코사인, 후보 안 최댓값 기준 0~1. 쓸 수 없으면 None"""
    if not terms:
        return None
    try:
        matrix = eng._get_tfidf_matrix()  # 임베딩이 있으면 지연 로드되므로 먼저 불러온다
    except ImportError:  # scikit-learn 이 없으면 단어 일치 신호는 끈다
        return None
    if eng.tfidf is None:
        return None
    query = eng.tfidf.transform([" ".join(terms)])
    raw = np.asarray((matrix[cand_idx] @ query.T).todense()).ravel()
    top = raw.max()
    return raw / top if top > 0 else np.zeros(len(cand_idx))


def _soft_score(cand_idx: np.ndarray, players: int, low_text: bool) -> np.ndarray:
    """보조 신호 평균: 추천 인원 적합도, (요청 시) 언어 의존도가 낮은 정도"""
    df = eng.df
    good = df["GoodPlayers"].to_numpy()[cand_idx]
    signals = [np.array([players in g for g in good], dtype=float)]
    if low_text:
        pct = pd.Series(df["LanguageEase"].to_numpy(dtype=float)[cand_idx]).rank(pct=True).to_numpy()
        signals.append(np.where(np.isnan(pct), 0.5, 1.0 - pct))
    return np.mean(signals, axis=0)


def natural_search(
    query: str,
    players: int,
    max_time: int,
    exclude_ids: list[int] | None = None,
    top_n: int = 5,
) -> list[dict]:
    client = gemini.get_client()
    index = _index
    if client is None or index is None:
        raise RuntimeError("Natural language search is not available")

    intent = _get_intent(client, query)
    sort_column = SORT_COLUMNS.get(intent.sort)

    df = eng.df
    mask = eng._condition_mask(players, max_time, MIN_RATING).to_numpy() & index.present
    mask &= df["NumUserRatings"].to_numpy() >= MIN_REVIEWS
    if exclude_ids:
        mask &= ~df["BGGId"].isin(exclude_ids).to_numpy()
    weight = df["GameWeight"].to_numpy(dtype=float)
    known = weight > 0
    if intent.weight_min is not None:
        mask &= ~known | (weight >= intent.weight_min)
    if intent.weight_max is not None:
        mask &= ~known | (weight <= intent.weight_max)
    if intent.age_max is not None:
        age = df["ComAgeRec"].to_numpy(dtype=float)
        mask &= ~(age > 0) | (age <= intent.age_max)
    for feats, names in ((eng.mechanics, intent.exclude_mechanics), (eng.themes, intent.exclude_themes)):
        if names:
            hit = feats.binary[:, _tag_columns(feats, names)].sum(axis=1)
            mask &= np.asarray(hit).ravel() == 0

    cand_idx = np.flatnonzero(mask)
    if len(cand_idx) == 0:
        return []

    # 키워드가 프로필 메타데이터(시리즈·제작자·국가)에 걸리는 후보가 하나라도 있으면 필수 조건으로 쓴다
    if intent.keywords:
        text_hit, meta_hit = keyword_matches(cand_idx, intent.keywords)
        hard = meta_hit.any(axis=0)
        if hard.any():
            keep = (text_hit | meta_hit)[:, hard].all(axis=1)
            cand_idx = cand_idx[keep]
            if len(cand_idx) == 0:
                return []

    tag_hits = np.zeros(len(cand_idx))
    include_total = (
        len(intent.include_mechanics) + len(intent.include_themes) + len(intent.categories) + len(intent.keywords)
    )
    matched: dict[str, np.ndarray] = {}
    tag_ratio = None
    if include_total:
        for key, feats, names in (
            ("mech", eng.mechanics, intent.include_mechanics),
            ("theme", eng.themes, intent.include_themes),
        ):
            if names:
                sub = feats.binary[cand_idx][:, _tag_columns(feats, names)].toarray() > 0
                matched[key] = sub
                tag_hits += sub.sum(axis=1)
        if intent.categories:
            cat_cols = [f"Cat:{n}" for n in intent.categories]
            tag_hits += (df[cat_cols].to_numpy()[cand_idx] > 0).sum(axis=1)
        if intent.keywords:
            tag_hits += keyword_hits(cand_idx, intent.keywords).sum(axis=1)
        if sort_column:
            # "가장 유명한 협력 게임": 태그가 하나라도 있는 게임 안에서만 순위를 매긴다
            keep = tag_hits > 0
            if not keep.any():
                return []
            cand_idx, tag_hits = cand_idx[keep], tag_hits[keep]
            matched = {k: v[keep] for k, v in matched.items()}
        tag_ratio = tag_hits / include_total

    # 장르 묘사가 없는 순위 질의("가장 유명한 게임")는 임베딩을 계산하지 않는다 (Gemini 호출도 줄어듦)
    embedding = None
    if intent.search_text:
        query_vec = _get_query_vector(client, intent.search_text, index.vectors.shape[1])
        raw = index.vectors[cand_idx] @ query_vec
        if index.profile_vectors is not None and PROFILE_VECTOR_WEIGHT > 0:
            pos = index.profile_pos[cand_idx]
            has = pos >= 0
            if has.any():
                prof_cos = index.profile_vectors[pos[has]] @ query_vec
                raw[has] = (1 - PROFILE_VECTOR_WEIGHT) * raw[has] + PROFILE_VECTOR_WEIGHT * prof_cos
        low, high = np.median(raw), raw.max()
        embedding = np.clip((raw - low) / max(high - low, 1e-6), 0.0, 1.0)

    word = _word_score(cand_idx, intent.terms)
    parts = [(w, v) for w, v in (
        (EMBEDDING_WEIGHT, embedding), (TAG_WEIGHT, tag_ratio), (WORD_WEIGHT, word)) if v is not None]
    if parts:
        similarity = sum(w * v for w, v in parts) / sum(w for w, _ in parts)
    else:
        similarity = np.zeros(len(cand_idx))

    if sort_column:
        picked = _sorted_positions(
            cand_idx, similarity, sort_column, top_n, narrow=embedding is not None, tag_hits=tag_hits
        )
        # 정렬 질의의 Score는 순위 (1.0, 0.8, ... 1위가 가장 높음)
        score = np.zeros(len(cand_idx))
        score[picked] = 1.0 - np.arange(len(picked)) / max(len(picked), 1)
    else:
        score = (
            SIMILARITY_WEIGHT * similarity
            + RATING_WEIGHT * eng.rating_score(cand_idx)
            + SOFT_WEIGHT * _soft_score(cand_idx, players, intent.low_text)
        )
        # 같은 시리즈(확장·버전·외전)는 한 게임만 남기고 다양화한다
        reps = group_series(cand_idx, score, tag_hits, "NumUserRatings")
        picked = reps[eng.diversify(cand_idx[reps], score[reps], top_n)]

    results = []
    for pos in picked:
        record = df.loc[int(cand_idx[pos]), eng.DEFAULT_COLUMNS].to_dict()
        record["Similarity"] = float(similarity[pos])
        record["Score"] = float(score[pos])
        record["MatchedMechanics"] = (
            [n for n, h in zip(intent.include_mechanics, matched["mech"][pos]) if h] if "mech" in matched else []
        )
        record["MatchedThemes"] = (
            [n for n, h in zip(intent.include_themes, matched["theme"][pos]) if h] if "theme" in matched else []
        )
        record["SortedBy"] = intent.sort
        results.append(record)
    return results


def group_series(
    cand_idx: np.ndarray, score: np.ndarray, tag_hits: np.ndarray, prefer_col: str
) -> np.ndarray:
    """시리즈마다 대표 한 게임의 cand_idx 안 위치를 반환 (시리즈 최고 점수 내림차순).
    대표 = 태그 일치가 가장 많은 구성원 중 prefer_col 이 큰 것 (같으면 리뷰 수가 많은 것)."""
    if len(cand_idx) == 0:
        return np.zeros(0, dtype=int)
    codes, _ = pd.factorize(series.KEYS[cand_idx])
    df = eng.df
    prefer = df[prefer_col].to_numpy(dtype=float)[cand_idx]
    reviews = df["NumUserRatings"].to_numpy(dtype=float)[cand_idx]
    order = np.lexsort((-reviews, -prefer, -np.asarray(tag_hits, dtype=float)))  # 마지막 키가 1순위
    _, first = np.unique(codes[order], return_index=True)
    reps = order[first]
    best = np.full(codes.max() + 1, -np.inf)
    np.maximum.at(best, codes, score)
    return reps[np.argsort(-best[codes[reps]], kind="stable")]


def _sorted_positions(
    cand_idx: np.ndarray, similarity: np.ndarray, column: str, top_n: int, narrow: bool,
    tag_hits: np.ndarray | None = None,
) -> np.ndarray:
    """정렬 질의: (장르 묘사가 있으면 유사도 상위 SORT_POOL개 안에서) column 값이 큰 순, 같으면 리뷰 수 순.
    반환값은 cand_idx 안에서의 위치 배열."""
    pos = np.arange(len(cand_idx))
    if narrow:
        pos = np.argsort(-similarity, kind="stable")[:SORT_POOL]
    df = eng.df
    values = df[column].to_numpy(dtype=float)[cand_idx[pos]]
    reviews = df["NumUserRatings"].to_numpy(dtype=float)[cand_idx[pos]]
    order = np.lexsort((-reviews, -values))  # 마지막 키가 1순위
    pos = pos[order]
    # 같은 시리즈는 한 게임만: 정렬 순위를 점수로 삼아 시리즈별 대표를 고른다
    hits = np.zeros(len(cand_idx)) if tag_hits is None else tag_hits
    rank_score = 1.0 - np.arange(len(pos)) / max(len(pos), 1)
    return pos[group_series(cand_idx[pos], rank_score, hits[pos], column)][:top_n]
