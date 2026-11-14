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

    def test_excludes_games_with_few_reviews(self):
        # 리뷰가 적은 무명 게임은 설명글이 짧고 일반적이라 짧은 질의와 가장 가깝게 나온다 → 후보에서 뺀다
        mask = eng._condition_mask(4, 120, 5.5) & (eng.df["NumUserRatings"] < ns.MIN_REVIEWS)
        idx = int(eng.df.index[mask][0])
        ns.set_index(make_index(idx))
        games = natural_search("obscure", 4, 120)
        self.assertTrue(games)
        self.assertNotIn(int(eng.df.at[idx, "BGGId"]), [g["BGGId"] for g in games])
        for g in games:
            self.assertGreaterEqual(g["NumUserRatings"], ns.MIN_REVIEWS)

    def test_weight_range_keeps_unknown_weight(self):
        # 난이도 정보가 없는 게임은 모두 리뷰 1,000개 미만이라 하한을 잠시 끄고 난이도 규칙만 확인
        mask = eng._condition_mask(4, 120, 5.5) & (eng.df["GameWeight"] == 0)
        idx = int(eng.df.index[mask][0])
        ns.set_index(make_index(idx))
        self.fake.intent = QueryIntent("x", weight_max=1.5)
        original = ns.MIN_REVIEWS
        ns.MIN_REVIEWS = 0
        try:
            games = natural_search("w", 4, 120)
        finally:
            ns.MIN_REVIEWS = original
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

    def test_corrupt_index_file_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.npz"
            path.write_bytes(b"not an npz file at all")
            self.assertIsNone(ns.load_index(path))
            np.savez(path, other=np.zeros(1))  # foreign npz without our keys
            self.assertIsNone(ns.load_index(path))

    def test_sanitize_maps_tag_names_case_insensitively(self):
        s = sanitize_intent(
            QueryIntent("x", include_mechanics=(" cooperative game ",), include_themes=("ECONOMIC",)),
            "q",
        )
        self.assertEqual(s.include_mechanics, ("Cooperative Game",))
        self.assertEqual(s.include_themes, ("Economic",))


class SortedSearchTest(unittest.TestCase):
    """'가장 유명한/평점 높은/최신' 질의: 설명글 유사도가 아니라 리뷰 수·평점·연도 순으로 고른다"""

    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        ns.clear_caches()
        e0 = np.zeros(8, dtype=np.float32)
        e0[0] = 1.0
        self.fake = FakeGeminiClient(query_vector=e0)
        set_client(self.fake)
        ns.set_index(make_index(idx_of("Pandemic")))

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        ns.clear_caches()

    def expected(self, column, players=4, max_time=120, tag=None):
        df = eng.df
        mask = eng._condition_mask(players, max_time, 5.5) & (df["NumUserRatings"] >= ns.MIN_REVIEWS)
        if tag is not None:
            col = int(np.flatnonzero(eng.mechanics.names == tag)[0])
            mask &= np.asarray(eng.mechanics.binary[:, col].toarray()).ravel() > 0
        top = df[mask].sort_values([column, "NumUserRatings"], ascending=False, kind="stable")
        return [int(i) for i in top["BGGId"].head(5)]

    def test_popularity_without_genre_sorts_by_reviews_and_skips_embedding(self):
        self.fake.intent = QueryIntent("", sort="popularity")
        games = natural_search("가장 유명한 게임", 4, 120)
        self.assertEqual([g["BGGId"] for g in games], self.expected("NumUserRatings"))
        self.assertTrue(all(g["SortedBy"] == "popularity" for g in games))
        self.assertFalse(any(c[0] == "embed_query" for c in self.fake.calls))

    def test_rating_and_newest_sort_by_their_columns(self):
        self.fake.intent = QueryIntent("", sort="rating")
        self.assertEqual([g["BGGId"] for g in natural_search("best rated", 4, 120)], self.expected("BayesAvgRating"))
        self.fake.intent = QueryIntent("", sort="newest")
        games = natural_search("newest", 4, 120)
        self.assertEqual([g["BGGId"] for g in games], self.expected("YearPublished"))
        self.assertTrue(all(g["SortedBy"] == "newest" for g in games))

    def test_popularity_within_include_tag(self):
        self.fake.intent = QueryIntent("", include_mechanics=("Cooperative Game",), sort="popularity")
        games = natural_search("가장 유명한 협력 게임", 4, 120)
        self.assertEqual([g["BGGId"] for g in games], self.expected("NumUserRatings", tag="Cooperative Game"))
        for g in games:
            self.assertEqual(g["MatchedMechanics"], ["Cooperative Game"])

    def test_genre_text_narrows_pool_before_sorting(self):
        # search_text가 있으면 임베딩 상위 SORT_POOL개 안에서만 정렬 → 가장 비슷한 게임(Pandemic)이 반드시 포함
        self.fake.intent = QueryIntent("cooperative disease fighting", sort="popularity")
        games = natural_search("가장 유명한 전염병 게임", 4, 120)
        self.assertIn(int(eng.df.at[idx_of("Pandemic"), "BGGId"]), [g["BGGId"] for g in games])
        reviews = [g["NumUserRatings"] for g in games]
        self.assertEqual(reviews, sorted(reviews, reverse=True))
        self.assertTrue(any(c[0] == "embed_query" for c in self.fake.calls))

    def test_relevance_keeps_similarity_ranking(self):
        self.fake.intent = QueryIntent("co-op")
        games = natural_search("co-op", 4, 60)
        self.assertEqual(games[0]["Name"], "Pandemic")
        self.assertTrue(all(g["SortedBy"] == "relevance" for g in games))

    def test_sanitize_keeps_blank_text_only_for_sorted_queries(self):
        self.assertEqual(sanitize_intent(QueryIntent(" ", sort="popularity"), "가장 유명한 게임").search_text, "")
        self.assertEqual(sanitize_intent(QueryIntent(" "), "원문").search_text, "원문")

    def test_refresh_excludes_shown_games_in_sorted_mode(self):
        self.fake.intent = QueryIntent("", sort="popularity")
        first = natural_search("가장 유명한 게임", 4, 120)
        second = natural_search("가장 유명한 게임", 4, 120, exclude_ids=[g["BGGId"] for g in first])
        self.assertTrue(second)
        self.assertFalse({g["BGGId"] for g in first} & {g["BGGId"] for g in second})


if __name__ == "__main__":
    unittest.main()
