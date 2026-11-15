"""
backend/build_game_profiles.py
후보 게임마다 Gemini로 영어 '플레이 경험 프로필'을 만들어 data/game_profiles.json 으로 저장 (오프라인 작업).
프로필은 검색(후보 추리기)에만 쓰고 사용자에게 직접 보여주지 않는다.

실행 (프로젝트 루트, GEMINI_API_KEY 필요):
    uv run --env-file .env python -m backend.build_game_profiles [--limit N] [--sample]

리뷰 1000개 이상 게임을 리뷰 많은 순으로 처리. 배치마다 저장하므로 중단 후 다시 실행하면 이어서 진행함.
--sample 은 시범용: 리뷰 많은 25개 + 리뷰 1000~3000개 구간에서 25개(고정 시드).
"""

import argparse
import json
import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from backend import features, gemini

PROFILES_PATH = Path(__file__).resolve().parent.parent / "data" / "game_profiles.json"
MIN_REVIEWS = 1000
DESIGNER_MIN_REVIEWS = 3000  # 이보다 리뷰가 적은 게임은 제작자 정보를 믿기 어려워 비움
BATCH_SIZE = 10
MAX_RETRIES = 5
BACKOFF_SECONDS = 2.0
MIN_WORDS, MAX_WORDS = 40, 200
MAX_ITEMS, MAX_ITEM_CHARS = 5, 60
SAMPLE_SEED = 0
_HANGUL = re.compile("[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")


def _engine():
    from backend import recommend_engine

    return recommend_engine


def profile_input(idx: int) -> dict:
    eng = _engine()
    row = eng.df.iloc[idx]
    cats = [c.removeprefix("Cat:") for c in features.CATEGORY_COLUMNS if row[c] > 0]
    mech = [str(n) for n in eng.mechanics.names[eng.mechanics.binary[idx].indices]]
    themes = [str(n) for n in eng.themes.names[eng.themes.binary[idx].indices]]
    return {
        "bgg_id": int(row["BGGId"]),
        "name": str(row["Name"]),
        "year": int(row["YearPublished"]),
        "mechanics": mech,
        "themes": themes,
        "categories": cats,
        "weight": round(float(row["GameWeight"]), 2),
        "age": float(row["ComAgeRec"]) if row["ComAgeRec"] > 0 else None,
        "players": f"{int(row['MinPlayers'])}-{int(row['MaxPlayers'])}",
        "playtime": f"{int(row['ComMinPlaytime'])}-{int(row['ComMaxPlaytime'])} min",
        "description": str(row["Description"])[:800],
        "include_designers": bool(row["NumUserRatings"] >= DESIGNER_MIN_REVIEWS),
    }


def _trim(items) -> tuple[str, ...]:
    out = [str(x).strip()[:MAX_ITEM_CHARS] for x in items if str(x).strip()]
    return tuple(out[:MAX_ITEMS])


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def clean_profile(
    p: gemini.GameProfile, name: str | None = None, include_designers: bool = True
) -> gemini.GameProfile | None:
    words = len(p.profile.split())
    if words < MIN_WORDS or words > MAX_WORDS or _HANGUL.search(p.profile):
        return None
    base = p.base_game
    if base is not None and name is not None and base.strip().casefold() == name.strip().casefold():
        base = None
    franchise = _trim(p.franchise)
    if name is not None:
        franchise = tuple(f for f in franchise if _norm(f) != _norm(name))
    return gemini.GameProfile(
        bgg_id=p.bgg_id,
        profile=p.profile.strip(),
        franchise=franchise,
        base_game=base[:MAX_ITEM_CHARS] if base else None,
        designers=_trim(p.designers) if include_designers else (),
        designer_countries=_trim(p.designer_countries) if include_designers else (),
    )


def _write_with_retry(client, games, sleep=time.sleep):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.write_profiles(games)
        except gemini.GeminiError as e:
            if attempt == MAX_RETRIES:
                raise
            wait = BACKOFF_SECONDS * 2 ** (attempt - 1)
            print(f"  실패({e}); {wait:.0f}초 후 재시도 {attempt}/{MAX_RETRIES - 1}")
            sleep(wait)
    raise AssertionError("unreachable")


def _load(out: Path) -> dict:
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    return {"model": gemini.PROFILE_MODEL, "created": "", "profiles": {}}


def _save(out: Path, data: dict) -> None:
    data["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def build(ids, out: Path, batch: int = BATCH_SIZE, limit: int | None = None, client=None, sleep=time.sleep) -> dict:
    """ids 순서대로 프로필 생성. out 에 이미 있는 id는 건너뜀. 반환: 통계"""
    eng = _engine()
    client = client or gemini.GoogleGeminiClient(_api_key())
    data = _load(out)
    done = data["profiles"]
    pos = {int(g): i for i, g in enumerate(eng.df["BGGId"])}
    todo = [int(i) for i in ids if str(int(i)) not in done and int(i) in pos]
    if limit is not None:
        todo = todo[:limit]
    stats = {"requested": len(todo), "generated": 0, "dropped": 0, "missing": 0}
    for b in range(0, len(todo), batch):
        chunk = todo[b : b + batch]
        games = [profile_input(pos[g]) for g in chunk]
        info = {g["bgg_id"]: g for g in games}
        got = {p.bgg_id: p for p in _write_with_retry(client, games, sleep)}
        for g in chunk:
            p = got.get(g)
            if p is None:
                stats["missing"] += 1
                continue
            cleaned = clean_profile(p, info[g]["name"], info[g]["include_designers"])
            if cleaned is None:
                stats["dropped"] += 1
                continue
            rec = asdict(cleaned)
            del rec["bgg_id"]
            done[str(g)] = rec
            stats["generated"] += 1
        data["model"] = gemini.PROFILE_MODEL
        _save(out, data)
        print(f"배치 {b // batch + 1}/{(len(todo) + batch - 1) // batch} 완료 (생성 {stats['generated']}, 제외 {stats['dropped']}, 누락 {stats['missing']})")
    return stats


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set. Put it in .env and run with `uv run --env-file .env ...`.")
    return key


def candidate_ids(sample: bool) -> list[int]:
    df = _engine().df
    pool = df[df["NumUserRatings"] >= MIN_REVIEWS].sort_values("NumUserRatings", ascending=False)
    if not sample:
        return [int(i) for i in pool["BGGId"]]
    top = pool.head(25)
    band = pool[(pool["NumUserRatings"] < 3000)]
    rng = np.random.default_rng(SAMPLE_SEED)
    pick = band.iloc[np.sort(rng.choice(len(band), size=min(25, len(band)), replace=False))]
    return [int(i) for i in [*top["BGGId"], *pick["BGGId"]]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="앞쪽 N개만 처리")
    parser.add_argument("--sample", action="store_true", help="시범용 50개 표본")
    parser.add_argument("--out", type=Path, default=PROFILES_PATH)
    args = parser.parse_args()
    _api_key()
    ids = candidate_ids(args.sample)
    print(f"후보 {len(ids)}개 (모델: {gemini.PROFILE_MODEL})")
    client = gemini.GoogleGeminiClient(_api_key())
    stats = build(ids, args.out, limit=args.limit, client=client)
    print(f"토큰 사용: {client.usage}")
    print(f"완료: {stats} -> {args.out}")


if __name__ == "__main__":
    main()
