import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini, profiles, rerank
from backend.gemini import GeminiError, RerankResult, set_client
from backend.limits import DailyBudget
from backend.recommend_engine import df
from tests.gemini_fake import FakeGeminiClient

IDS = [int(x) for x in df["BGGId"].iloc[:30]]


class RerankTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._budget = gemini.budget
        self._profiles = dict(profiles.PROFILES)
        gemini.budget = DailyBudget(100)
        self.fake = FakeGeminiClient()
        set_client(self.fake)

    def tearDown(self):
        gemini._client = self._client
        gemini.budget = self._budget
        profiles.PROFILES.clear()
        profiles.PROFILES.update(self._profiles)

    def set_result(self, interp="Read as: fine.", ids=(), weak=False):
        self.fake.rerank_result = RerankResult(interp, tuple(ids), weak)

    def test_facts_fields(self):
        profiles.PROFILES.pop(IDS[0], None)
        profiles.PROFILES[IDS[1]] = {"profile": "A calm family game."}
        f0, f1 = rerank.rerank_facts(0), rerank.rerank_facts(1)
        for f in (f0, f1):
            for key in ("bgg_id", "name", "year", "mechanics", "themes", "categories", "weight",
                        "age", "players", "good_players", "playtime", "reviews", "rating", "profile"):
                self.assertIn(key, f)
            self.assertNotIn("web_mentioned", f)
        self.assertEqual(f1["profile"], "A calm family game.")
        desc = df.iloc[0]["Description"]
        self.assertEqual(f0["profile"], (desc if isinstance(desc, str) else "")[:150])
        self.assertLessEqual(len(f0["profile"]), 150)
        self.assertTrue(rerank.rerank_facts(0, frozenset({IDS[0]}))["web_mentioned"])
        self.assertFalse(rerank.rerank_facts(0, frozenset({-1}))["web_mentioned"])

    def test_filters_unknown_and_duplicate_ids(self):
        self.set_result(ids=[IDS[2], 999999999, IDS[2], IDS[0], IDS[5]])
        out = rerank.rerank("q", [0, 1, 2])
        self.assertEqual(out.ranked_ids, (IDS[2], IDS[0]))

    def test_caps_at_max_ids(self):
        self.set_result(ids=IDS)
        out = rerank.rerank("q", list(range(30)))
        self.assertEqual(out.ranked_ids, tuple(IDS[:20]))

    def test_interpretation_cleaned(self):
        cases = {
            "  Read as: a calm game.  ": "Read as: a calm game.",
            "a calm game": "Read as: a calm game",
            "Read as: 협력 게임": "",
            "Read as: " + "x" * 300: "",
        }
        for raw, want in cases.items():
            self.set_result(interp=raw)
            self.assertEqual(rerank.rerank("q", [0]).interpretation, want, raw)

    def test_weak_match_passes_through(self):
        self.set_result(weak=True)
        self.assertTrue(rerank.rerank("q", [0]).weak_match)

    def test_forwards_players_and_max_time(self):
        rerank.rerank("q", [0], players=2, max_time=45)
        self.assertEqual(self.fake.calls[-1][3:], (2, 45))

    def test_charges_budget_and_propagates_errors(self):
        rerank.rerank("q", [0])
        self.assertEqual(gemini.budget.try_spend(100), False)  # 1 already spent
        self.assertEqual(self.fake.calls[0][0], "rerank")
        self.assertEqual([g["bgg_id"] for g in self.fake.calls[0][2]], [IDS[0]])
        self.fake.error = GeminiError("boom")
        with self.assertRaises(GeminiError):
            rerank.rerank("q", [0])
        gemini.budget = DailyBudget(0)
        with self.assertRaises(gemini.BudgetExceeded):
            rerank.rerank("q", [0])


if __name__ == "__main__":
    unittest.main()
