import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import evaluate_natural as ev, natural_search as ns, recommend_engine as eng
from backend.gemini import QueryIntent

QUERY_FILE = Path(__file__).resolve().parent.parent / "data" / "natural_eval_queries.json"
SPEC_EXAMPLES = [
    "할머니, 할아버지와 함께하기 좋은 게임",
    "어린아이들과 하기 좋은 동물이 나오는 게임",
    "술자리에서",
    "긴장감 있는",
    "머리 안 쓰는",
    "전쟁 게임",
    "가장 유명한 게임",
    "스타워즈 테마의 보드게임",
    "한국인이 만든 보드게임",
    "동물들도 이해하기 쉬운 게임",
]
# No answer can be derived from the dataset; the user supplies good ids during review.
PENDING_GOOD = {"한국인이 만든 보드게임"}
TYPES = {"audience", "mood", "genre", "ranking", "external", "no_answer", "series"}


def bgg_id(name: str) -> int:
    return int(eng.df.loc[eng.df["Name"] == name, "BGGId"].iloc[0])


class MetricsTest(unittest.TestCase):
    def test_hit_and_precision(self):
        self.assertTrue(ev.hit_at_k([1, 2, 3], {3}, 5))
        self.assertFalse(ev.hit_at_k([1, 2], {9}, 5))
        self.assertEqual(ev.precision_at_k([1, 2, 3, 4, 5], {1, 2}, 5), 0.4)

    def test_series_duplicate(self):
        pandemic, legacy, catan = (
            bgg_id("Pandemic"), bgg_id("Pandemic Legacy: Season 1"), bgg_id("Catan"),
        )
        self.assertTrue(ev.has_series_duplicate([pandemic, legacy]))
        self.assertFalse(ev.has_series_duplicate([pandemic, catan]))

    def test_unreachable_flags_games_outside_pool(self):
        small = eng.df[(eng.df["MaxPlayers"] < 5) & (eng.df["NumUserRatings"] >= ns.MIN_REVIEWS)]
        gid = int(small["BGGId"].iloc[0])
        entry = {"query": "q", "players": 5, "max_time": 600, "good": [gid]}
        self.assertEqual(ev.unreachable(entry), [gid])

    def test_run_with_fake_search(self):
        gid = bgg_id("Pandemic")
        rows = [{"BGGId": gid, "Name": "Pandemic"}, {"BGGId": 1, "Name": "Other"}]
        entry = {"query": "co-op", "type": "genre", "players": 4, "max_time": 120,
                 "good": [gid], "bad": [], "expect_weak_match": False}
        result = ev.run([entry], "fake", search=lambda q, p, t, top_n: rows)
        self.assertEqual(result["summary"]["hit_at_5"], 1.0)
        self.assertEqual(result["per_query"][0]["names"], ["Pandemic", "Other"])
        self.assertEqual(result["label"], "fake")
        self.assertIn("genre", result["summary"]["by_type"])


class DiskCacheTest(unittest.TestCase):
    def setUp(self):
        ns.clear_caches()

    def tearDown(self):
        ns.clear_caches()

    def test_disk_cache_round_trip(self):
        intent = QueryIntent("co-op", include_mechanics=("Cooperative Game",), weight_max=2.5)
        vec = np.arange(4, dtype=np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            ns._intent_cache.put("q", intent)
            ns._vector_cache.put("co-op", vec)
            ev.DiskCache(path).save()
            ns.clear_caches()
            ev.DiskCache(path).load()
        self.assertEqual(ns._intent_cache.get("q"), intent)
        np.testing.assert_array_equal(ns._vector_cache.get("co-op"), vec)

    def test_fresh_intents_skips_stored_intents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            ns._intent_cache.put("q", QueryIntent("x"))
            ev.DiskCache(path).save()
            ns.clear_caches()
            ev.DiskCache(path).load(fresh_intents=True)
        self.assertIsNone(ns._intent_cache.get("q"))


class QueryFileTest(unittest.TestCase):
    def test_query_file_is_valid(self):
        entries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(entries), 40)
        queries = [e["query"] for e in entries]
        self.assertEqual(len(set(queries)), 40)
        counts = {t: 0 for t in TYPES}
        for e in entries:
            self.assertIn(e["type"], TYPES)
            counts[e["type"]] += 1
            self.assertIsInstance(e["expect_weak_match"], bool)
            self.assertTrue(e["good"] or e["type"] == "no_answer" or e["query"] in PENDING_GOOD, e["query"])
            self.assertLessEqual(len(e["good"]), 15, e["query"])
            self.assertEqual(e["type"] == "no_answer", e["expect_weak_match"], e["query"])
        self.assertTrue(all(c >= 4 for c in counts.values()), counts)
        self.assertTrue(any(any("가" <= ch <= "힣" for ch in q) for q in queries))
        self.assertTrue(any(q.isascii() for q in queries))
        for q in SPEC_EXAMPLES:
            self.assertIn(q, queries)
        for e in entries:
            self.assertEqual(ev.unreachable(e), [], e["query"])
            self.assertFalse(set(e["good"]) & set(e["bad"]), e["query"])


if __name__ == "__main__":
    unittest.main()
