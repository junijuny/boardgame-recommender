"""후보 게임 재정렬: Gemini에 후보의 사실 정보를 주고 순서·해석·약한 매칭 여부를 받아 걸러낸다."""

try:
    from backend import features, gemini, profiles, recommend_engine as eng
    from backend.explain import _HANGUL, _names, _range
except ImportError:
    import features
    import gemini
    import profiles
    import recommend_engine as eng
    from explain import _HANGUL, _names, _range

RERANK_MAX_IDS = 20
MAX_INTERPRETATION_CHARS = 200
FALLBACK_PROFILE_CHARS = 150
PREFIX = "Read as: "


def rerank_facts(idx: int, web_ids: frozenset[int] = frozenset()) -> dict:
    row = eng.df.iloc[idx]
    bgg_id = int(row["BGGId"])
    weight = float(row["GameWeight"])
    age = float(row["ComAgeRec"])
    entry = profiles.PROFILES.get(bgg_id)
    text = entry.get("profile") if entry else None
    if not isinstance(text, str) or not text.strip():
        description = row["Description"]
        text = (description if isinstance(description, str) else "")[:FALLBACK_PROFILE_CHARS]
    facts = {
        "bgg_id": bgg_id,
        "name": str(row["Name"]),
        "year": int(row["YearPublished"]),
        "mechanics": _names(eng.mechanics, idx),
        "themes": _names(eng.themes, idx),
        "categories": [c.removeprefix("Cat:") for c in features.CATEGORY_COLUMNS if row[c] > 0],
        "weight": round(weight, 2) if weight > 0 else None,
        "age": age if age > 0 else None,
        "players": _range(row["MinPlayers"], row["MaxPlayers"]),
        "good_players": [int(p) for p in row["GoodPlayers"]],
        "playtime": _range(row["ComMinPlaytime"], row["ComMaxPlaytime"], " min"),
        "reviews": int(row["NumUserRatings"]),
        "rating": round(float(row["BayesAvgRating"]), 1),
        "profile": text,
    }
    if web_ids:
        facts["web_mentioned"] = bgg_id in web_ids
    return facts


def _clean_interpretation(text) -> str:
    text = text.strip() if isinstance(text, str) else ""
    if not text or len(text) > MAX_INTERPRETATION_CHARS or _HANGUL.search(text):
        return ""
    if not text.startswith(PREFIX):
        text = PREFIX + text
    return text


def rerank(
    query: str,
    cand_rows: list[int],
    web_ids: frozenset[int] = frozenset(),
    players: int | None = None,
    max_time: int | None = None,
    min_time: int | None = None,
) -> gemini.RerankResult:
    client = gemini.get_client()
    if client is None:
        raise gemini.GeminiError("Gemini client is not configured")
    gemini.charge()
    games = [rerank_facts(i, web_ids) for i in cand_rows]
    if players is not None or max_time is not None or min_time is not None:
        raw = client.rerank(query, games, players=players, max_time=max_time, min_time=min_time)
    else:
        raw = client.rerank(query, games)
    allowed = {g["bgg_id"] for g in games}
    ids = [i for i in dict.fromkeys(raw.ranked_ids) if i in allowed]
    return gemini.RerankResult(
        interpretation=_clean_interpretation(raw.interpretation),
        ranked_ids=tuple(ids[:RERANK_MAX_IDS]),
        weak_match=bool(raw.weak_match),
    )
