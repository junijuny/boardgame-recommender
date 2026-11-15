"""자연어 검색 품질 평가: 질의 세트에 대한 hit@5, precision@5, recall@N 등을 계산한다.

실행: uv run --env-file .env python -m backend.evaluate_natural --label <name> [--fresh-intents]
"""

import argparse
import dataclasses
import json
from pathlib import Path

import numpy as np

try:
    from backend import gemini, natural_search, series
    from backend import recommend_engine as eng
except ImportError:  # Docker image runs from backend/
    import gemini
    import natural_search
    import recommend_engine as eng
    import series

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUERY_FILE = DATA_DIR / "natural_eval_queries.json"
CACHE_FILE = DATA_DIR / "natural_eval_cache.json"
RESULTS_DIR = DATA_DIR / "natural_eval_results"
K = 5


def hit_at_k(ids: list[int], good: set[int], k: int) -> bool:
    return any(i in good for i in ids[:k])


def precision_at_k(ids: list[int], good: set[int], k: int) -> float:
    return sum(i in good for i in ids[:k]) / k


def has_series_duplicate(ids: list[int]) -> bool:
    position = {int(b): i for i, b in enumerate(eng.df["BGGId"])}
    keys = [series.KEYS[position[int(i)]] for i in ids]
    return len(set(keys)) < len(keys)


def unreachable(entry: dict) -> list[int]:
    """good 중 이 항목의 인원·시간 조건에서 검색 후보 풀에 들어가지 못하는 게임."""
    df = eng.df
    pool = eng._condition_mask(entry["players"], entry["max_time"], natural_search.MIN_RATING)
    pool = pool.to_numpy() & (df["NumUserRatings"].to_numpy() >= natural_search.MIN_REVIEWS)
    index = natural_search._index
    if index is not None:
        pool &= index.present
    reachable = set(df["BGGId"].to_numpy()[pool].tolist())
    return [g for g in entry["good"] if g not in reachable]


def _mean(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 4) if values else None


def _summarize(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["hit_at_5"] is not None]
    weak = [r["weak_match"] for r in rows if r["weak_match"] is not None]
    return {
        "queries": len(rows),
        "hit_at_5": _mean([float(r["hit_at_5"]) for r in scored]),
        "precision_at_5": _mean([r["precision_at_5"] for r in scored]),
        "recall_at_n": _mean([r["recall_at_n"] for r in scored]),
        "series_duplicate_rate": _mean([float(r["series_duplicate"]) for r in rows]),
        "bad_in_top5_rate": _mean([float(r["bad_in_top5"]) for r in rows]),
        "weak_match_rate": _mean([float(w) for w in weak]) if weak else None,
    }


def run(entries: list[dict], label: str, search=natural_search.natural_search, recall_n: int = 25) -> dict:
    per_query = []
    for entry in entries:
        good, bad = set(entry["good"]), set(entry["bad"])
        # 근거 검색 결과는 평가에 쓸 수 없다: 웹 검색은 항상 끈다
        found = search(entry["query"], entry["players"], entry["max_time"], top_n=K, allow_web=False)
        rows = found.games
        top = [int(r["BGGId"]) for r in rows][:K]
        # 재현율은 재정렬 전 후보 묶음(상위 recall_n)에서 계산한다
        ids = [int(i) for i in found.shortlist_ids][:recall_n]
        scored = bool(good)
        per_query.append({
            "query": entry["query"],
            "type": entry["type"],
            "ids": top,
            "names": [r["Name"] for r in rows[:K]],
            "hit_at_5": hit_at_k(top, good, K) if scored else None,
            "precision_at_5": precision_at_k(top, good, K) if scored else None,
            "recall_at_n": len(good & set(ids)) / len(good) if scored else None,
            "series_duplicate": has_series_duplicate(top),
            "bad_in_top5": any(i in bad for i in top),
            "weak_match": bool(found.weak_match),
            "expect_weak_match": entry["expect_weak_match"],
        })
    summary = _summarize(per_query)
    summary["by_type"] = {
        t: _summarize([r for r in per_query if r["type"] == t])
        for t in sorted({r["type"] for r in per_query})
    }
    return {"label": label, "summary": summary, "per_query": per_query}


class DiskCache:
    """평가 중 만든 의도·질의 벡터를 파일에 저장해 재실행 시 Gemini 호출을 줄인다."""

    def __init__(self, path: Path):
        self.path = path

    def load(self, fresh_intents: bool = False) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        fields = {f.name for f in dataclasses.fields(gemini.QueryIntent)}
        if not fresh_intents:
            for key, raw in data.get("intents", {}).items():
                kwargs = {k: tuple(v) if isinstance(v, list) else v for k, v in raw.items() if k in fields}
                natural_search._intent_cache.put(key, gemini.QueryIntent(**kwargs))
        for text, vec in data.get("vectors", {}).items():
            natural_search._vector_cache.put(text, np.asarray(vec, dtype=np.float32))

    def save(self) -> None:
        data = {
            "intents": {k: dataclasses.asdict(v) for k, v in natural_search._intent_cache._data.items()},
            "vectors": {k: v.tolist() for k, v in natural_search._vector_cache._data.items()},
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _fmt(value) -> str:
    return "  -  " if value is None else f"{value:.2f}"


def print_table(result: dict) -> None:
    print(f"== {result['label']} ==")
    print(f"{'type':<11}{'n':>3}  hit@5  prec@5  recall  dup   bad   weak")
    groups = {"ALL": result["summary"], **result["summary"]["by_type"]}
    for name, s in groups.items():
        print(
            f"{name:<11}{s['queries']:>3}  {_fmt(s['hit_at_5'])}  {_fmt(s['precision_at_5'])}   "
            f"{_fmt(s['recall_at_n'])}   {_fmt(s['series_duplicate_rate'])}  "
            f"{_fmt(s['bad_in_top5_rate'])}  {_fmt(s['weak_match_rate'])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--fresh-intents", action="store_true", help="저장된 의도를 무시(프롬프트 변경 후)")
    args = parser.parse_args()

    entries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    cache = DiskCache(CACHE_FILE)
    cache.load(fresh_intents=args.fresh_intents)
    try:
        result = run(entries, args.label)
    finally:
        cache.save()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{args.label}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print_table(result)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
