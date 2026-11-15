import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini, natural_search as ns, profiles, recommend_engine as eng, series
from backend.gemini import QueryIntent, set_client
from tests.gemini_fake import FakeGeminiClient

search_full = ns.natural_search


def natural_search(*args, **kwargs):
    """Games only; tests of the result object call search_full."""
    return search_full(*args, **kwargs).games

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
            self.assertEqual(charge.call_count, 3)
            natural_search("co-op", 4, 60)
            self.assertEqual(charge.call_count, 3)

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


class AudienceSignalTest(unittest.TestCase):
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

    def test_sanitize_keywords_and_terms(self):
        raw = ("Star Wars", "스타워즈", "", "x" * 200, "star wars", "A", "B", "C")
        s = sanitize_intent(QueryIntent("a", keywords=raw, terms=raw), "q")
        self.assertEqual(s.keywords, ("Star Wars", "A", "B"))
        self.assertEqual(s.terms, ("Star Wars", "A", "B"))

    def test_sanitize_age_and_categories(self):
        self.assertEqual(sanitize_intent(QueryIntent("a", age_max=40), "q").age_max, 18.0)
        self.assertEqual(sanitize_intent(QueryIntent("a", age_max=0), "q").age_max, 2.0)
        self.assertIsNone(sanitize_intent(QueryIntent("a"), "q").age_max)
        s = sanitize_intent(QueryIntent("a", categories=("family", "Nope")), "q")
        self.assertEqual(s.categories, ("Family",))

    def test_age_max_filters_known_ages(self):
        self.fake.intent = QueryIntent("family fun", age_max=8)
        games = natural_search("q", 4, 120)
        self.assertEqual(len(games), 5)
        for g in games:
            age = eng.df.loc[eng.df["BGGId"] == g["BGGId"], "ComAgeRec"].iloc[0]
            self.assertTrue(age == 0 or age <= 8)

    def test_keyword_ranking_query(self):
        self.fake.intent = QueryIntent("", keywords=("Star Wars",), sort="popularity")
        games = natural_search("스타워즈 게임", 2, 180)
        self.assertTrue(games)
        pattern = re.compile(r"\bstar wars\b", re.IGNORECASE)
        for g in games:
            row = eng.df.loc[eng.df["BGGId"] == g["BGGId"]].iloc[0]
            self.assertTrue(pattern.search(f"{row['Name']} {row['Description']}"))
        reviews = [g["NumUserRatings"] for g in games]
        self.assertEqual(reviews, sorted(reviews, reverse=True))

    def test_ranking_keyword_with_no_match_is_empty(self):
        self.fake.intent = QueryIntent("", keywords=("Zzyzx Qwerty",), sort="popularity")
        self.assertEqual(natural_search("q", 2, 180), [])

    def test_category_counts_as_include_tag(self):
        # 임베딩 점수를 모두 같게 만들어 태그 일치만 순위를 가른다
        ns.set_index(ns.GeminiIndex(vectors=np.tile(np.eye(1, 8, dtype=np.float32), (len(eng.df), 1)),
                                    present=np.ones(len(eng.df), dtype=bool)))
        self.fake.intent = QueryIntent("party game", categories=("Party",))
        games = natural_search("q", 4, 120)
        top = eng.df.loc[eng.df["BGGId"] == games[0]["BGGId"]].iloc[0]
        self.assertEqual(top["Cat:Party"], 1)

    def test_terms_word_match_raises_score(self):
        players, minutes = 4, 120
        mask = eng._condition_mask(players, minutes, ns.MIN_RATING).to_numpy().copy()
        mask &= eng.df["NumUserRatings"].to_numpy() >= ns.MIN_REVIEWS
        has_word = eng.df["Description"].str.contains(r"\bzombies\b", case=False, regex=True).to_numpy()
        fits = np.array([players in g for g in eng.df["GoodPlayers"]])
        a = int(np.flatnonzero(mask & has_word & fits)[0])
        b = int(np.flatnonzero(mask & ~has_word & fits)[0])
        keep = {int(eng.df.at[a, "BGGId"]), int(eng.df.at[b, "BGGId"])}
        exclude = [int(i) for i in eng.df["BGGId"] if int(i) not in keep]
        ns.set_index(ns.GeminiIndex(vectors=np.tile(np.eye(1, 8, dtype=np.float32), (len(eng.df), 1)),
                                    present=np.ones(len(eng.df), dtype=bool)))
        self.fake.intent = QueryIntent("something", terms=("zombies",))
        with mock.patch.object(eng, "rating_score", lambda idx: np.zeros(len(idx))):
            games = natural_search("q", players, minutes, exclude_ids=exclude)
        self.assertEqual(len(games), 2)
        self.assertEqual(games[0]["BGGId"], int(eng.df.at[a, "BGGId"]))
        self.assertGreater(games[0]["Score"], games[1]["Score"])

    def test_missing_audience_data_is_safe(self):
        idx = idx_of("Pandemic")
        cols = ["ComAgeRec", "LanguageEase", "GoodPlayers"]
        saved = {c: eng.df.at[idx, c] for c in cols}
        try:
            eng.df.at[idx, "ComAgeRec"] = 0.0
            eng.df.at[idx, "LanguageEase"] = np.nan
            eng.df.at[idx, "GoodPlayers"] = ()
            self.fake.intent = QueryIntent("co-op", low_text=True, age_max=10)
            games = natural_search("q", 4, 120)
        finally:
            for c, v in saved.items():
                eng.df.at[idx, c] = v
        self.assertEqual(len(games), 5)
        self.assertEqual(games[0]["Name"], "Pandemic")

    def test_word_match_off_without_tfidf(self):
        self.fake.intent = QueryIntent("something", terms=("zombies",))
        # _word_score 가 _get_tfidf_matrix() 로 tfidf 를 다시 채울 수 있으니 함께 막아 끈 경로를 실제로 탄다
        with mock.patch.object(eng, "tfidf", None), mock.patch.object(
            eng, "_get_tfidf_matrix", return_value=None
        ), mock.patch.object(ns, "_word_score", wraps=ns._word_score) as word:
            self.assertEqual(len(natural_search("q", 4, 120)), 5)
            self.assertTrue(word.called)
        with mock.patch.object(eng, "tfidf", None), mock.patch.object(eng, "_get_tfidf_matrix", return_value=None):
            self.assertIsNone(ns._word_score(np.arange(5), ("zombies",)))


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
        # 같은 시리즈는 정렬 기준이 가장 높은 게임 하나만
        top = top[~pd.Series(ns.series.KEYS[top.index], index=top.index).duplicated()]
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


class SeriesGroupingTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        ns.clear_caches()
        e0 = np.zeros(8, dtype=np.float32)
        e0[0] = 1.0
        self.fake = FakeGeminiClient(intent=QueryIntent("co-op"), query_vector=e0)
        set_client(self.fake)
        ns.set_index(make_index(idx_of("Pandemic")))

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        ns.clear_caches()

    def group(self, names, score, hits, col="NumUserRatings"):
        cand = np.array([idx_of(n) for n in names])
        return [names[i] for i in ns.group_series(cand, np.array(score, dtype=float), np.array(hits, dtype=float), col)]

    def test_group_series_keeps_most_reviewed(self):
        got = self.group(["Pandemic", "Pandemic Legacy: Season 1", "Catan"], [0.5, 0.9, 0.4], [0, 0, 0])
        self.assertEqual(got, ["Pandemic", "Catan"])

    def test_group_series_prefers_tag_match(self):
        got = self.group(["Carcassonne", "Carcassonne: Star Wars"], [0.5, 0.6], [0, 1])
        self.assertEqual(got, ["Carcassonne: Star Wars"])

    def test_group_series_ranking_uses_sort_column(self):
        got = self.group(["Pandemic", "Pandemic Legacy: Season 1"], [0.9, 0.5], [0, 0], "BayesAvgRating")
        self.assertEqual(got, ["Pandemic Legacy: Season 1"])

    def assert_one_per_series(self, games):
        idx = [int(eng.df.index[eng.df["BGGId"] == g["BGGId"]][0]) for g in games]
        keys = [ns.series.KEYS[i] for i in idx]
        self.assertEqual(len(keys), len(set(keys)))

    def test_search_results_have_one_per_series(self):
        games = natural_search("co-op", 4, 120, top_n=10)
        self.assertEqual(len(games), 10)
        self.assert_one_per_series(games)

    def test_ranking_results_have_one_per_series(self):
        self.fake.intent = QueryIntent("", sort="popularity")
        games = natural_search("가장 유명한 게임", 4, 120, top_n=10)
        self.assertEqual(len(games), 10)
        self.assert_one_per_series(games)


class ProfileSearchTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        self._profiles = profiles.PROFILES
        self._keys = series.KEYS
        ns.clear_caches()
        e0 = np.zeros(8, dtype=np.float32)
        e0[0] = 1.0
        self.fake = FakeGeminiClient(intent=QueryIntent("anything"), query_vector=e0)
        set_client(self.fake)
        ns.set_index(make_index(idx_of("Pandemic")))

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        profiles.PROFILES = self._profiles
        series.set_keys(self._keys)
        ns.clear_caches()

    def write_npz(self, path, ids, vectors):
        np.savez(path, ids=np.asarray(ids), vectors=vectors.astype(np.float16),
                 model_name=gemini.EMBED_MODEL, dim=np.int32(vectors.shape[1]), doc_version=np.int32(1))

    def test_profile_vector_weight(self):
        n, dim = len(eng.df), gemini.EMBED_DIM
        rng = np.random.default_rng(1)
        base = rng.normal(size=(n, dim)).astype(np.float32)
        base[:, :2] = 0.0
        base /= np.linalg.norm(base, axis=1, keepdims=True)
        target, other = idx_of("Catan"), idx_of("Pandemic")
        # other: old vector matches the query best; target: only its profile vector matches
        base[other] = 0.0
        base[other, 0] = 1.0
        pv = np.zeros((1, dim), dtype=np.float32)
        pv[0, 1] = 1.0
        query = np.zeros(dim, dtype=np.float32)
        query[0] = 1.0
        ids = eng.df["BGGId"].to_numpy()
        with tempfile.TemporaryDirectory() as d:
            base_path, prof_path = Path(d) / "g.npz", Path(d) / "p.npz"
            self.write_npz(base_path, ids, base)
            self.write_npz(prof_path, ids[[target]], pv)
            index = ns.load_index(base_path, prof_path)
            missing = ns.load_index(base_path, Path(d) / "missing.npz")
        self.assertIsNone(missing.profile_vectors)
        self.assertEqual(int((index.profile_pos >= 0).sum()), 1)
        self.assertTrue(np.allclose(index.vectors[target], base[target], atol=1e-3))  # old vector kept

        def top(weight, q, idx=index):
            ns.clear_caches()
            self.fake.query_vector = q
            ns.set_index(idx)
            with mock.patch.object(ns, "PROFILE_VECTOR_WEIGHT", weight):
                return natural_search("q", 4, 120)[0]["Name"]

        self.assertEqual(top(0.0, query), "Pandemic")  # w=0: old behavior
        q_prof = np.zeros(dim, dtype=np.float32)
        q_prof[1] = 1.0
        self.assertEqual(top(1.0, q_prof), "Catan")  # w=1: profile vector wins
        self.assertNotEqual(top(0.0, q_prof), "Catan")
        self.assertNotEqual(top(1.0, q_prof, missing), "Catan")  # no profile file: old behavior

    def pool_ids(self, n=2):
        mask = eng._condition_mask(4, 120, ns.MIN_RATING).to_numpy() & (
            eng.df["NumUserRatings"].to_numpy() >= ns.MIN_REVIEWS)
        return [int(i) for i in eng.df["BGGId"].to_numpy()[np.flatnonzero(mask)[:n]]]

    def test_metadata_keyword_is_hard_filter(self):
        a, b = self.pool_ids()
        profiles.PROFILES = {a: {"designer_countries": ["South Korea"]}, b: {"designer_countries": ["South Korea"]}}
        self.fake.intent = QueryIntent("anything", keywords=("Korea",))
        games = natural_search("q", 4, 120, top_n=10)
        self.assertTrue(games)
        for g in games:
            desc = eng.df.loc[eng.df["BGGId"] == g["BGGId"], "Description"].iloc[0]
            self.assertTrue(g["BGGId"] in (a, b) or "korea" in f"{g['Name']} {desc}".lower(), g["Name"])

    def test_metadata_keyword_without_hits_is_soft(self):
        profiles.PROFILES = {}
        self.fake.intent = QueryIntent("anything", keywords=("Nowhereland",))
        self.assertEqual(len(natural_search("q", 4, 120)), 5)

    def test_two_metadata_keywords_are_anded(self):
        a, b, c = self.pool_ids(3)
        profiles.PROFILES = {
            a: {"franchise": ["Xenon"]},
            b: {"designers": ["Yolanda"]},
            c: {"franchise": ["Xenon"], "designers": ["Yolanda"]},
        }
        self.fake.intent = QueryIntent("anything", keywords=("Xenon", "Yolanda"))
        games = natural_search("q", 4, 120, top_n=50)
        ids = {g["BGGId"] for g in games}
        self.assertIn(c, ids)
        self.assertFalse({a, b} & ids)
        for g in games:
            desc = eng.df.loc[eng.df["BGGId"] == g["BGGId"], "Description"].iloc[0]
            text = f"{g['Name']} {desc}".lower()
            self.assertTrue(g["BGGId"] == c or ("xenon" in text and "yolanda" in text), g["Name"])

    def test_keyword_hits_matches_metadata(self):
        a, _ = self.pool_ids()
        profiles.PROFILES = {a: {"designers": ["Zzyzx Qwerty"], "franchise": [], "designer_countries": []}}
        i = int(eng.df.index[eng.df["BGGId"] == a][0])
        self.assertTrue(ns.keyword_hits(np.array([i]), ("Qwerty",))[0, 0])
        self.assertFalse(ns.keyword_hits(np.array([i]), ("Qwert",))[0, 0])

    def test_base_game_joins_series(self):
        a, b = idx_of("Catan"), idx_of("Lost Cities")
        base = {int(eng.df.loc[b, "BGGId"]): "Catan"}
        self.assertNotEqual(series.KEYS[a], series.KEYS[b])
        series.set_keys(series.series_keys(eng.df, series.MIN_REVIEWS, base_games=base))
        self.assertEqual(series.KEYS[a], series.KEYS[b])
        self.fake.intent = QueryIntent("co-op")
        names = {g["Name"] for g in natural_search("q", 4, 120, top_n=20)}
        self.assertFalse({"Catan", "Lost Cities"} <= names)


class RerankSearchTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        self._wall = ns.RERANK_WALL_SECONDS
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
        ns.RERANK_WALL_SECONDS = self._wall
        ns.clear_caches()

    def rerank_calls(self):
        return [c for c in self.fake.calls if c[0] == "rerank"]

    def shortlist(self):
        ids = search_full("co-op", 4, 60).shortlist_ids
        ns.clear_caches()
        self.fake.calls.clear()
        return ids

    def test_rerank_order_is_used(self):
        short = self.shortlist()
        want = tuple(reversed(short[:8]))
        self.fake.rerank_result = gemini.RerankResult("Read as: x.", want, False)
        r = search_full("co-op", 4, 60)
        self.assertEqual([g["BGGId"] for g in r.games], list(want[:5]))
        self.assertEqual(r.interpretation, "Read as: x.")
        self.assertFalse(r.weak_match)
        self.assertIsNone(r.web)
        self.assertEqual(len(self.rerank_calls()[-1][2]), ns.SHORTLIST_SIZE)

    def test_pads_to_five_and_flags_weak(self):
        short = self.shortlist()
        self.fake.rerank_result = gemini.RerankResult("Read as: x.", tuple(short[3:5]), False)
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)
        self.assertEqual([g["BGGId"] for g in r.games[:2]], short[3:5])
        self.assertTrue(r.weak_match)
        self.assertEqual(len({g["BGGId"] for g in r.games}), 5)

    def test_model_weak_flag_passes_through(self):
        short = self.shortlist()
        self.fake.rerank_result = gemini.RerankResult("Read as: x.", tuple(short[:5]), True)
        self.assertTrue(search_full("co-op", 4, 60).weak_match)

    def test_empty_interpretation_is_none(self):
        short = self.shortlist()
        self.fake.rerank_result = gemini.RerankResult("", tuple(short[:5]), False)
        self.assertIsNone(search_full("co-op", 4, 60).interpretation)

    def test_dedupes_series_in_rerank_output(self):
        a, b = idx_of("Pandemic"), idx_of("Pandemic Legacy: Season 1")
        ids = [int(eng.df.loc[a, "BGGId"]), int(eng.df.loc[b, "BGGId"])]
        self.assertEqual(series.KEYS[a], series.KEYS[b])
        short = self.shortlist()
        others = [i for i in short if i not in ids][:6]
        # re-rank 출력에 같은 시리즈 두 개가 직접 들어와도 페이지 구성 단계에서 하나만 남아야 한다
        result = gemini.RerankResult("Read as: x.", tuple(ids + others), False)
        with mock.patch.object(ns.rerank, "rerank", return_value=result):
            games = search_full("co-op", 4, 60).games
        got = [g["BGGId"] for g in games]
        self.assertEqual(len(got), 5)
        self.assertEqual(sum(1 for i in ids if i in got), 1)
        keys = [series.KEYS[int(eng.df.index[eng.df["BGGId"] == g][0])] for g in got]
        self.assertEqual(len(set(keys)), 5)

    def test_refresh_uses_cache(self):
        short = self.shortlist()
        self.fake.rerank_result = gemini.RerankResult("Read as: x.", tuple(short[:12]), False)
        first = search_full("co-op", 4, 60)
        second = search_full("co-op", 4, 60, exclude_ids=[g["BGGId"] for g in first.games])
        self.assertEqual([g["BGGId"] for g in second.games], short[5:10])
        self.assertEqual(second.interpretation, "Read as: x.")
        self.assertEqual(len(self.rerank_calls()), 1)

    def test_refresh_cache_miss_calls_again_without_storing(self):
        first = search_full("co-op", 4, 60)
        shown = [g["BGGId"] for g in first.games]
        ns._rerank_cache.clear()
        self.fake.calls.clear()
        search_full("co-op", 4, 60, exclude_ids=shown)
        self.assertEqual(len(self.rerank_calls()), 1)
        self.assertIsNone(ns._rerank_cache.get(("co-op", 4, 60)))
        search_full("co-op", 4, 60, exclude_ids=shown)
        self.assertEqual(len(self.rerank_calls()), 2)

    def test_first_page_is_cached_by_normalized_query(self):
        search_full(" Co-Op ", 4, 60)
        self.assertIsNotNone(ns._rerank_cache.get(("co-op", 4, 60)))

    def test_rerank_failure_falls_back(self):
        short = self.shortlist()
        want = tuple(reversed(short[:8]))
        self.fake.rerank_result = gemini.RerankResult("Read as: x.", want, False)
        reranked = [g["BGGId"] for g in search_full("co-op", 4, 60).games]
        ns.clear_caches()
        self.fake.rerank_result = None
        self.fake.rerank_error = gemini.GeminiError("boom")
        r = search_full("co-op", 4, 60)
        got = [g["BGGId"] for g in r.games]
        self.assertEqual(len(got), 5)
        self.assertNotEqual(got, reranked)  # 재정렬 순서를 쓰지 않는다
        self.assertEqual(reranked, list(want[:5]))
        self.assertTrue(set(got) <= set(short))
        self.assertIsNone(r.interpretation)
        self.assertIs(r.weak_match, False)
        self.assertIsNone(ns._rerank_cache.get(("co-op", 4, 60)))

    def test_rerank_timeout_falls_back(self):
        real = self.fake.rerank

        def slow(query, games):
            time.sleep(0.5)
            return real(query, games)

        self.fake.rerank = slow
        ns.RERANK_WALL_SECONDS = 0.05
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)
        self.assertIsNone(r.interpretation)
        self.assertFalse(r.weak_match)
        self.assertIsNone(ns._rerank_cache.get(("co-op", 4, 60)))

    def test_budget_exhausted_for_rerank_falls_back(self):
        self.fake.rerank_error = gemini.BudgetExceeded("limit")
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)
        self.assertIsNone(r.interpretation)

    def test_ranking_query_skips_rerank(self):
        self.fake.intent = QueryIntent("", sort="popularity")
        r = search_full("most popular", 4, 60)
        self.assertEqual(r.interpretation, "Ranked by number of BGG reviews.")
        self.assertFalse(r.weak_match)
        self.assertEqual(self.rerank_calls(), [])
        self.assertEqual(len(r.shortlist_ids), ns.SHORTLIST_SIZE)
        self.assertEqual(r.shortlist_ids[:5], [g["BGGId"] for g in r.games])
        for sort, copy in (("rating", "Ranked by BGG rating."), ("newest", "Ranked by release year.")):
            self.fake.intent = QueryIntent("", sort=sort)
            self.assertEqual(search_full(sort, 4, 60).interpretation, copy)

    def test_exhausted_candidates_returns_empty(self):
        seen: list[int] = []
        for _ in range(500):
            r = search_full("co-op", 4, 60, exclude_ids=seen)
            if not r.games:
                break
            ids = [g["BGGId"] for g in r.games]
            self.assertFalse(set(ids) & set(seen))
            seen += ids
        else:
            self.fail("never exhausted")
        self.assertEqual(r.games, [])
        self.assertEqual(r.shortlist_ids, [])
        self.assertIsNone(r.interpretation)
        self.assertEqual(len(seen), len(set(seen)))


class WebSearchNaturalTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        self._budget = ns.web_search.web_budget
        ns.web_search.web_budget = ns.web_search.limits.DailyBudget(100)
        ns.clear_caches()
        e0 = np.zeros(8, dtype=np.float32)
        e0[0] = 1.0
        self.fake = FakeGeminiClient(
            intent=QueryIntent("co-op", include_mechanics=("Cooperative Game",), needs_web=True),
            query_vector=e0,
        )
        set_client(self.fake)
        ns.set_index(make_index(idx_of("Pandemic")))
        short = search_full("co-op", 4, 60).shortlist_ids
        self.short_names = [str(eng.df.loc[eng.df["BGGId"] == i, "Name"].iloc[0]) for i in short]
        ns.clear_caches()
        self.fake.calls.clear()

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        ns.web_search.web_budget = self._budget
        ns.clear_caches()

    def calls(self, name):
        return [c for c in self.fake.calls if c[0] == name]

    def answer(self, names, html="<div>s</div>"):
        self.fake.web_answer = gemini.WebAnswer("\n".join(names) + "\n\nSummary here.", html, 1)

    def test_no_web_call_without_needs_web(self):
        self.fake.intent = QueryIntent("co-op", include_mechanics=("Cooperative Game",))
        r = search_full("co-op", 4, 60)
        self.assertEqual(self.calls("web_search"), [])
        self.assertIsNone(r.web)

    def test_disabled_by_env(self):
        with mock.patch.dict("os.environ", {"NATURAL_WEB_SEARCH": "0"}):
            r = search_full("co-op", 4, 60)
        self.assertEqual(self.calls("web_search"), [])
        self.assertIsNone(r.web)

    def test_web_ids_hard_filter_when_five_or_more(self):
        names = self.short_names[10:16]
        self.answer(names)
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)
        self.assertTrue({g["Name"] for g in r.games} <= set(names))
        facts = self.calls("rerank")[0][2]
        self.assertTrue(all(g["web_mentioned"] for g in facts))

    def test_web_query_sanitized(self):
        mk = lambda q: ns.sanitize_intent(QueryIntent("x", needs_web=True, web_query=q), "raw")
        self.assertEqual(mk("  Korean games  ").web_query, "Korean games")
        self.assertEqual(mk("한국 게임").web_query, "")
        self.assertEqual(mk("x" * 121).web_query, "")

    def test_lookup_uses_web_query_else_raw(self):
        self.answer(self.short_names[:2])
        self.fake.intent = QueryIntent("co-op", include_mechanics=("Cooperative Game",),
                                       needs_web=True, web_query="english query")
        search_full("raw query", 4, 60)
        self.assertEqual(self.calls("web_search")[-1][1], "english query")
        ns.clear_caches()
        self.fake.intent = QueryIntent("co-op", include_mechanics=("Cooperative Game",), needs_web=True)
        search_full("raw query", 4, 60)
        self.assertEqual(self.calls("web_search")[-1][1], "raw query")

    def _meta_only_first(self):
        def fake_matches(cand_idx, keywords):
            text = np.zeros((len(cand_idx), len(keywords)), dtype=bool)
            meta = np.zeros_like(text)
            meta[0, :] = True
            return text, meta
        return mock.patch.object(ns, "keyword_matches", fake_matches)

    def test_metadata_keyword_is_soft_when_web_succeeded(self):
        self.fake.intent = QueryIntent("co-op", keywords=("Zzz",), needs_web=True)
        self.answer(self.short_names[:2])
        with self._meta_only_first():
            r = search_full("co-op", 4, 60)
        self.assertIsNotNone(r.web)
        self.assertEqual(len(r.games), 5)

    def test_metadata_keyword_is_hard_when_web_failed(self):
        self.fake.intent = QueryIntent("co-op", keywords=("Zzz",), needs_web=True)
        self.fake.web_error = gemini.GeminiError("boom")
        with self._meta_only_first():
            r = search_full("co-op", 4, 60)
        self.assertIsNone(r.web)
        self.assertEqual(len(r.games), 1)

    def test_many_ids_of_one_series_stay_soft(self):
        self.fake.web_answer = gemini.WebAnswer("Ticket to Ride\n\nSummary.", "<div>s</div>", 1)
        pool = ns.web_search.match_names("Ticket to Ride")
        self.assertGreater(len(pool), 5)
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)
        self.assertIsNotNone(r.web)

    def test_web_ids_soft_when_fewer(self):
        self.answer(self.short_names[10:12])
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)
        facts = self.calls("rerank")[0][2]
        self.assertEqual(sum(1 for g in facts if g["web_mentioned"]), 2)
        self.assertGreater(len(facts), 2)

    def test_web_result_attached(self):
        self.answer(self.short_names[:2], html="<div>unique suggestions</div>")
        r = search_full("co-op", 4, 60)
        self.assertEqual(r.web["suggestions_html"], "<div>unique suggestions</div>")
        self.assertEqual(r.web["summary"], "Summary here.")

    def test_web_query_never_cached(self):
        self.answer(self.short_names[:2])
        search_full("co-op", 4, 60)
        search_full("co-op", 4, 60)
        self.assertEqual(len(self.calls("web_search")), 2)
        self.assertEqual(len(self.calls("rerank")), 2)
        self.assertIsNone(ns._rerank_cache.get(("co-op", 4, 60)))

    def test_web_failure_falls_back(self):
        self.fake.web_error = gemini.GeminiError("boom")
        r = search_full("co-op", 4, 60)
        self.assertIsNone(r.web)
        self.assertEqual(len(r.games), 5)

    def test_web_timeout_falls_back(self):
        release = threading.Event()
        self.addCleanup(release.set)

        def slow(query):  # never calls the real lookup; unblocked at teardown
            release.wait(5)
            return None

        ns.WEB_WALL_SECONDS = 0.05
        try:
            with mock.patch.object(ns.web_search, "lookup", slow):
                r = search_full("co-op", 4, 60)
        finally:
            ns.WEB_WALL_SECONDS = gemini.WEB_TIMEOUT_SECONDS
        self.assertIsNone(r.web)
        self.assertEqual(len(r.games), 5)

    def test_low_ranked_web_match_still_reaches_page(self):
        old = ns.SHORTLIST_SIZE
        ns.SHORTLIST_SIZE = 60
        try:
            deep = search_full("co-op", 4, 60).shortlist_ids
        finally:
            ns.SHORTLIST_SIZE = old
        ns.clear_caches()
        self.assertGreater(len(deep), 45)
        name = str(eng.df.loc[eng.df["BGGId"] == deep[40], "Name"].iloc[0])
        self.assertNotIn(name, self.short_names)
        self.answer([name])
        r = search_full("co-op", 4, 60)
        self.assertIn(name, [g["Name"] for g in r.games])
        self.assertIn(deep[40], r.shortlist_ids)

    def test_weak_match_when_fewer_than_three_web_games_on_page(self):
        self.answer(self.short_names[10:12])
        self.assertTrue(search_full("co-op", 4, 60).weak_match)

    def test_not_weak_with_three_web_games(self):
        self.answer(self.short_names[10:13])
        self.assertFalse(search_full("co-op", 4, 60).weak_match)

    def test_rerank_unexpected_error_falls_back(self):
        self.fake.rerank_error = RuntimeError("boom")
        r = search_full("co-op", 4, 60)
        self.assertEqual(len(r.games), 5)


if __name__ == "__main__":
    unittest.main()
