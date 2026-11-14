import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini, natural_search as ns, recommend_engine as eng
from backend.gemini import QueryIntent, set_client
from tests.gemini_fake import FakeGeminiClient

natural_search = ns.natural_search
sanitize_intent = ns.sanitize_intent


def idx_of(name: str) -> int:
    return int(eng.df.index[eng.df["Name"] == name][0])


def has_tag(features, bgg_id: int, name: str) -> bool:
    row = int(eng.df.index[eng.df["BGGId"] == bgg_id][0])
    col = int(np.flatnonzero(features.names == name)[0])
    return features.binary[row, col] > 0


def make_index(top_idx: int, dim: int = 8) -> ns.GeminiIndex:
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(len(eng.df), dim)).astype(np.float32)
    vecs[:, 0] = 0.0
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs[top_idx] = 0.0
    vecs[top_idx, 0] = 1.0
    return ns.GeminiIndex(vectors=vecs, present=np.ones(len(eng.df), dtype=bool))


class NaturalSearchTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        ns.clear_caches()
        e0 = np.zeros(8, dtype=np.float32)
        e0[0] = 1.0
        self.fake = FakeGeminiClient(
            intent=QueryIntent("co-op", include_mechanics=("Cooperative Game",)), query_vector=e0
        )
        set_client(self.fake)
        ns.set_index(make_index(idx_of("Pandemic")))

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        ns.clear_caches()

    def test_returns_five_matching_conditions_with_fields(self):
        games = natural_search("co-op", players=4, max_time=60)
        self.assertEqual(len(games), 5)
        for g in games:
            self.assertLessEqual(g["MinPlayers"], 4)
            self.assertGreaterEqual(g["MaxPlayers"], 4)
            self.assertLessEqual(g["ComMaxPlaytime"], 60)
            for key in ("Similarity", "Score", "MatchedMechanics", "MatchedThemes"):
                self.assertIn(key, g)
        self.assertEqual(games[0]["Name"], "Pandemic")
        self.assertEqual(games[0]["MatchedMechanics"], ["Cooperative Game"])

    def test_exclude_mechanics_removes_games(self):
        self.fake.intent = QueryIntent("co-op", exclude_mechanics=("Dice Rolling",))
        games = natural_search("q", 4, 120)
        self.assertTrue(games)
        for g in games:
            self.assertFalse(has_tag(eng.mechanics, g["BGGId"], "Dice Rolling"))

    def test_weight_range_keeps_unknown_weight(self):
        mask = eng._condition_mask(4, 120, 5.5) & (eng.df["GameWeight"] == 0)
        idx = int(eng.df.index[mask][0])
        ns.set_index(make_index(idx))
        self.fake.intent = QueryIntent("x", weight_max=1.5)
        games = natural_search("w", 4, 120)
        self.assertEqual(games[0]["BGGId"], int(eng.df.at[idx, "BGGId"]))
        for g in games:
            self.assertTrue(g["GameWeight"] == 0 or g["GameWeight"] <= 1.5)

    def test_sanitize_drops_unknown_and_fixes_weights(self):
        s = sanitize_intent(
            QueryIntent(" ", include_mechanics=("Not A Tag", "Cooperative Game", "Cooperative Game"),
                        weight_min=4.8, weight_max=0.2),
            "원문",
        )
        self.assertEqual(s.include_mechanics, ("Cooperative Game",))
        self.assertEqual((s.weight_min, s.weight_max), (1.0, 4.8))
        self.assertEqual(s.search_text, "원문")

    def test_sanitize_conflict_removed_from_include(self):
        s = sanitize_intent(
            QueryIntent("a", include_mechanics=("Dice Rolling", "Cooperative Game"),
                        exclude_mechanics=("Dice Rolling",)), "q")
        self.assertEqual(s.include_mechanics, ("Cooperative Game",))
        self.assertEqual(s.exclude_mechanics, ("Dice Rolling",))

    def test_no_tags_still_returns_results(self):
        self.fake.intent = QueryIntent("something fun")
        self.assertEqual(len(natural_search("뭔가 신나는 거", 4, 60)), 5)

    def test_exclude_ids_and_cache(self):
        first = natural_search("co-op", 4, 60)
        second = natural_search("co-op", 4, 60, exclude_ids=[g["BGGId"] for g in first])
        self.assertFalse({g["BGGId"] for g in first} & {g["BGGId"] for g in second})
        self.assertEqual(sum(c[0] == "extract_intent" for c in self.fake.calls), 1)
        self.assertEqual(sum(c[0] == "embed_query" for c in self.fake.calls), 1)

    def test_charge_only_on_cache_miss(self):
        from unittest import mock
        with mock.patch.object(gemini, "charge") as charge:
            natural_search("co-op", 4, 60)
            self.assertEqual(charge.call_count, 2)
            natural_search("co-op", 4, 60)
            self.assertEqual(charge.call_count, 2)

    def test_unavailable_without_client(self):
        set_client(None)
        with self.assertRaises(RuntimeError):
            natural_search("co-op", 4, 60)

    def test_index_rejected_on_model_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "e.npz"
            np.savez(path, ids=np.array([1]), vectors=np.zeros((1, gemini.EMBED_DIM), np.float16),
                     model_name="other", dim=np.int32(gemini.EMBED_DIM))
            self.assertIsNone(ns.load_index(path))
            np.savez(path, ids=np.array([1]), vectors=np.zeros((1, gemini.EMBED_DIM), np.float16),
                     model_name=gemini.EMBED_MODEL, dim=np.int32(gemini.EMBED_DIM))
            self.assertIsNotNone(ns.load_index(path))
            self.assertIsNone(ns.load_index(Path(d) / "missing.npz"))


if __name__ == "__main__":
    unittest.main()
