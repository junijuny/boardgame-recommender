"""자연어 검색 엔진: Gemini 의도 추출 + 임베딩 유사도 + 태그 일치 + 평점."""

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from backend import features, gemini, recommend_engine as eng
except ImportError:
    import features
    import gemini
    import recommend_engine as eng

MIN_RATING = 5.5
EMBEDDING_WEIGHT = 0.8   # 유사도 중 임베딩 비중 (나머지는 태그 일치)
SIMILARITY_WEIGHT = 0.75  # 최종 점수 중 유사도 비중 (나머지는 평점)
CACHE_SIZE = 256


@dataclass
class GeminiIndex:
    vectors: np.ndarray  # float32 (len(df), dim), 없는 게임은 0 행
    present: np.ndarray  # bool (len(df),)


def load_index(path: Path = features.GEMINI_EMBEDDINGS_PATH) -> GeminiIndex | None:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=False)
    if str(data["model_name"]) != gemini.EMBED_MODEL or int(data["dim"]) != gemini.EMBED_DIM:
        return None
    position = pd.Series(np.arange(len(data["ids"])), index=data["ids"])
    rows = position.reindex(eng.df["BGGId"].to_numpy())
    present = rows.notna().to_numpy()
    vectors = np.zeros((len(eng.df), data["vectors"].shape[1]), dtype=np.float32)
    vectors[present] = data["vectors"][rows[present].astype(int).to_numpy()].astype(np.float32)
    return GeminiIndex(vectors=vectors, present=present)


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


def _clean_tags(names, vocab: set[str], drop: set[str] = frozenset()) -> tuple[str, ...]:
    out: list[str] = []
    for name in names:
        if name in vocab and name not in drop and name not in out:
            out.append(name)
    return tuple(out)


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

    return gemini.QueryIntent(
        search_text=(intent.search_text or "").strip() or raw_query,
        include_mechanics=_clean_tags(intent.include_mechanics, mech_vocab, set(exclude_mechanics)),
        exclude_mechanics=exclude_mechanics,
        include_themes=_clean_tags(intent.include_themes, theme_vocab, set(exclude_themes)),
        exclude_themes=exclude_themes,
        weight_min=low,
        weight_max=high,
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
    query_vec = _get_query_vector(client, intent.search_text, index.vectors.shape[1])

    df = eng.df
    mask = eng._condition_mask(players, max_time, MIN_RATING).to_numpy() & index.present
    if exclude_ids:
        mask &= ~df["BGGId"].isin(exclude_ids).to_numpy()
    weight = df["GameWeight"].to_numpy(dtype=float)
    known = weight > 0
    if intent.weight_min is not None:
        mask &= ~known | (weight >= intent.weight_min)
    if intent.weight_max is not None:
        mask &= ~known | (weight <= intent.weight_max)
    for feats, names in ((eng.mechanics, intent.exclude_mechanics), (eng.themes, intent.exclude_themes)):
        if names:
            hit = feats.binary[:, _tag_columns(feats, names)].sum(axis=1)
            mask &= np.asarray(hit).ravel() == 0

    cand_idx = np.flatnonzero(mask)
    if len(cand_idx) == 0:
        return []

    raw = index.vectors[cand_idx] @ query_vec
    low, high = np.median(raw), raw.max()
    embedding = np.clip((raw - low) / max(high - low, 1e-6), 0.0, 1.0)

    matched: dict[str, np.ndarray] = {}
    include_total = len(intent.include_mechanics) + len(intent.include_themes)
    if include_total:
        tag_hits = np.zeros(len(cand_idx))
        for key, feats, names in (
            ("mech", eng.mechanics, intent.include_mechanics),
            ("theme", eng.themes, intent.include_themes),
        ):
            if names:
                sub = feats.binary[cand_idx][:, _tag_columns(feats, names)].toarray() > 0
                matched[key] = sub
                tag_hits += sub.sum(axis=1)
        similarity = EMBEDDING_WEIGHT * embedding + (1 - EMBEDDING_WEIGHT) * tag_hits / include_total
    else:
        similarity = embedding
    score = SIMILARITY_WEIGHT * similarity + (1 - SIMILARITY_WEIGHT) * eng.rating_score(cand_idx)

    results = []
    for pos in eng.diversify(cand_idx, score, top_n):
        record = df.loc[int(cand_idx[pos]), eng.DEFAULT_COLUMNS].to_dict()
        record["Similarity"] = float(similarity[pos])
        record["Score"] = float(score[pos])
        record["MatchedMechanics"] = (
            [n for n, h in zip(intent.include_mechanics, matched["mech"][pos]) if h] if "mech" in matched else []
        )
        record["MatchedThemes"] = (
            [n for n, h in zip(intent.include_themes, matched["theme"][pos]) if h] if "theme" in matched else []
        )
        results.append(record)
    return results
