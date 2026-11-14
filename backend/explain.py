"""추천 이유 한 문장 생성: 게임 사실 정보를 Gemini에 주고 결과를 걸러서 캐시한다."""

import re
import threading
from collections import OrderedDict
from typing import Literal

try:
    from backend import gemini, recommend_engine as eng
except ImportError:
    import gemini
    import recommend_engine as eng

CACHE_SIZE = 1024
DESCRIPTION_CHARS = 600
MAX_REASON_CHARS = 300
_HANGUL = re.compile("[ㄱ-ㆎ가-힣]")

_cache: OrderedDict[tuple[str, str, int], str] = OrderedDict()
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _names(features, idx: int) -> list[str]:
    return [str(features.names[c]) for c in features.binary[idx].indices]


def _range(lo, hi, suffix: str = "") -> str:
    lo, hi = int(lo), int(hi)
    return (str(lo) if lo == hi else f"{lo}-{hi}") + suffix


def game_facts(idx: int) -> dict:
    row = eng.df.iloc[idx]
    weight = float(row["GameWeight"])
    description = row["Description"]
    if not isinstance(description, str):
        description = ""
    return {
        "bgg_id": int(row["BGGId"]),
        "name": str(row["Name"]),
        "year": int(row["YearPublished"]),
        "players": _range(row["MinPlayers"], row["MaxPlayers"]),
        "playtime": _range(row["ComMinPlaytime"], row["ComMaxPlaytime"], " min"),
        "weight": weight if weight > 0 else None,
        "mechanics": _names(eng.mechanics, idx),
        "themes": _names(eng.themes, idx),
        "description": description[:DESCRIPTION_CHARS],
    }


def _cache_get(key):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key, value: str) -> None:
    with _lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def explain_games(
    mode: Literal["similar", "query"], basis: str, game_ids: list[int]
) -> dict[int, str]:
    basis_facts = None
    if mode == "similar":
        row = eng.get_game_by_name(basis)
        if row is None:
            raise LookupError("Game not found")
        basis_facts = game_facts(eng.df.index.get_loc(row.name))

    id_to_idx = {int(b): i for i, b in enumerate(eng.df["BGGId"])}
    ids = [i for i in dict.fromkeys(game_ids) if i in id_to_idx]
    basis_key = basis.strip().lower()

    result: dict[int, str] = {}
    missing: list[int] = []
    for bgg_id in ids:
        cached = _cache_get((mode, basis_key, bgg_id))
        if cached is None:
            missing.append(bgg_id)
        else:
            result[bgg_id] = cached
    if not missing:
        return result

    client = gemini.get_client()
    if client is None:
        raise gemini.GeminiError("Gemini client is not configured")
    gemini.charge()
    raw = client.explain(
        mode, basis, basis_facts, [game_facts(id_to_idx[i]) for i in missing]
    )

    wanted = set(missing)
    for bgg_id, text in raw.items():
        if bgg_id not in wanted or not isinstance(text, str):
            continue
        text = text.strip()
        if not text or len(text) > MAX_REASON_CHARS or _HANGUL.search(text):
            continue
        _cache_put((mode, basis_key, bgg_id), text)
        result[bgg_id] = text
    return result
