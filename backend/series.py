"""Series keys: group versions, expansions and spin-offs of one game under one key."""
import re

import numpy as np
import pandas as pd

try:
    from backend import profiles, recommend_engine as eng
except ImportError:  # Docker image runs from backend/
    import profiles
    import recommend_engine as eng

MIN_REVIEWS = 1000


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def _label(family: str) -> str:
    return _norm(family.split(" (")[0])


def series_keys(
    df: pd.DataFrame, min_reviews: int, base_games: dict[int, str] | None = None
) -> np.ndarray:
    base_games = base_games or {}
    names = [_norm(n) for n in df["Name"]]
    ids = df["BGGId"].tolist()
    families = [f if isinstance(f, str) else "" for f in df["Family"]]
    reviews = df["NumUserRatings"].tolist()
    keys = np.empty(len(df), dtype=object)

    for i, (family, name) in enumerate(zip(families, names)):
        label = _label(family) if family else ""
        if label and f" {label}" in f" {name}":
            keys[i] = "f:" + label

    # Most-reviewed row per normalized name, among rows that can act as a base game.
    base_row: dict[str, int] = {}
    for i, name in enumerate(names):
        if reviews[i] >= min_reviews and (name not in base_row or reviews[i] > reviews[base_row[name]]):
            base_row[name] = i

    for i, original in enumerate(df["Name"]):
        if keys[i] is not None:
            continue
        if ids[i] in base_games:
            base = _norm(base_games[ids[i]])
        elif ":" in original:
            base = _norm(original.split(":", 1)[0])
        else:
            base = ""
        j = base_row.get(base)
        if j is None or j == i:
            keys[i] = "n:" + names[i]
            continue
        if keys[j] is None:
            keys[j] = "n:" + names[j]
        keys[i] = keys[j]
    return keys


def profile_base_games(df: pd.DataFrame, game_profiles: dict[int, dict]) -> dict[int, str]:
    """프로필의 base_game (자기 이름과 같은 값은 제외)"""
    names = dict(zip(df["BGGId"].tolist(), df["Name"].tolist()))
    out = {}
    for bgg_id, p in game_profiles.items():
        base = p.get("base_game")
        if base and bgg_id in names and _norm(base) != _norm(names[bgg_id]):
            out[bgg_id] = base
    return out


KEYS = series_keys(eng.df, MIN_REVIEWS, base_games=profile_base_games(eng.df, profiles.PROFILES))


def set_keys(keys: np.ndarray) -> None:
    global KEYS
    KEYS = keys
