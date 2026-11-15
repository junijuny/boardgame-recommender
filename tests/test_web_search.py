import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini, limits, recommend_engine as eng, web_search
from backend.gemini import WebAnswer
from tests.gemini_fake import FakeGeminiClient


def bgg_id(name: str) -> int:
    return int(eng.df.loc[eng.df["Name"] == name, "BGGId"].iloc[0])


class WebSearchTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._budget = web_search.web_budget
        self._gbudget = gemini.budget
        web_search.web_budget = limits.DailyBudget(100)
        gemini.budget = limits.DailyBudget(100)
        self.fake = FakeGeminiClient()
        gemini.set_client(self.fake)

    def tearDown(self):
        gemini._client = self._client
        web_search.web_budget = self._budget
        gemini.budget = self._gbudget

    def test_match_names(self):
        ids = web_search.match_names("Catan\nPandemic Legacy: Season 1\nNot A Game")
        self.assertIn(bgg_id("Catan"), ids)
        self.assertIn(bgg_id("Pandemic Legacy: Season 1"), ids)
        self.assertTrue(all(isinstance(i, int) for i in ids))

    def test_match_name_before_colon_and_list_marks(self):
        ids = web_search.match_names("- catan!\n2) Pandemic Legacy")
        self.assertIn(bgg_id("Catan"), ids)
        self.assertIn(bgg_id("Pandemic Legacy: Season 1"), ids)

    def test_lookup_returns_ids_and_unmodified_html(self):
        self.fake.web_answer = WebAnswer("Catan\n\nA short summary.", "<div>x</div>", 1)
        ids, info = web_search.lookup("q")
        self.assertIn(bgg_id("Catan"), ids)  # "Catan: ..." spin-offs match by the name before the colon too
        self.assertEqual(info, {"summary": "A short summary.", "suggestions_html": "<div>x</div>"})

    def test_missing_suggestions_is_failure(self):
        self.fake.web_answer = WebAnswer("Catan\n\nSummary.", "", 1)
        self.assertIsNone(web_search.lookup("q"))

    def test_budget_spent_returns_none(self):
        web_search.web_budget = limits.DailyBudget(0)
        self.assertIsNone(web_search.lookup("q"))
        self.assertEqual(self.fake.calls, [])

    def test_error_returns_none(self):
        self.fake.web_error = gemini.GeminiError("boom")
        self.assertIsNone(web_search.lookup("q"))

    def test_spends_search_count(self):
        self.fake.web_answer = WebAnswer("Catan", "<div>x</div>", 3)
        web_search.lookup("q")
        self.assertEqual(web_search.web_budget.remaining(), 97)
        self.assertEqual(gemini.budget.remaining(), 99)  # also charged once to the general budget

    def test_lookup_passes_query_through(self):
        web_search.lookup("my english query")
        self.assertEqual(self.fake.calls[-1], ("web_search", "my english query"))

    def test_spends_at_least_one(self):
        self.fake.web_answer = WebAnswer("Catan", "<div>x</div>", 0)
        web_search.lookup("q")
        self.assertEqual(web_search.web_budget.remaining(), 99)

    def test_web_norm_strips_accents_and_apostrophes(self):
        self.assertEqual(web_search._web_norm("Tzolk'in"), web_search._web_norm("Tzolkin"))
        self.assertEqual(web_search._web_norm("Café"), web_search._web_norm("Cafe"))

    def test_match_names_accent_and_apostrophe_insensitive(self):
        df = pd.DataFrame({"BGGId": [1, 2], "Name": ["Tzolk'in: The Mayan Calendar", "Café"],
                           "NumUserRatings": [5000, 5000]})
        old = web_search._names
        web_search._names = None
        try:
            with mock.patch.object(web_search.eng, "df", df):
                self.assertEqual(web_search.match_names("Tzolkin"), frozenset({1}))
                self.assertEqual(web_search.match_names("Cafe"), frozenset({2}))
        finally:
            web_search._names = old

    def test_extra_searches_spend_only_remaining(self):
        web_search.web_budget = limits.DailyBudget(3)
        self.fake.web_answer = WebAnswer("Catan", "<div>x</div>", 10)
        self.assertIsNotNone(web_search.lookup("q"))
        self.assertEqual(web_search.web_budget.remaining(), 0)

    def test_general_budget_exhausted_spends_no_web_budget(self):
        gemini.budget = limits.DailyBudget(0)
        self.assertIsNone(web_search.lookup("q"))
        self.assertEqual(web_search.web_budget.remaining(), 100)


if __name__ == "__main__":
    unittest.main()
