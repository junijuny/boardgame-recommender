import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini
from backend.limits import DailyBudget
from tests.gemini_fake import FakeGeminiClient


class GeminiModuleTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._budget = gemini.budget

    def tearDown(self):
        gemini._client = self._client
        gemini.budget = self._budget

    def test_prefix_formats(self):
        self.assertEqual(gemini.query_text("co-op"), "task: search result | query: co-op")
        self.assertEqual(gemini.document_text("Catan", "Trading."), "title: Catan | text: Trading.")
        self.assertEqual(gemini.document_text("", "x"), "title: none | text: x")

    def test_charge_raises_when_budget_spent(self):
        gemini.budget = DailyBudget(1)
        gemini.charge()
        with self.assertRaises(gemini.BudgetExceeded):
            gemini.charge()

    def test_no_key_means_no_client(self):
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            gemini._client = gemini._UNSET
            self.assertIsNone(gemini.get_client())

    def test_empty_key_means_no_client(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            gemini._client = gemini._UNSET
            self.assertIsNone(gemini.get_client())

    def test_set_client_overrides(self):
        fake = FakeGeminiClient()
        gemini.set_client(fake)
        self.assertIs(gemini.get_client(), fake)

    def test_set_client_none_forces_unavailable(self):
        gemini.set_client(None)
        self.assertIsNone(gemini.get_client())

    def test_fake_records_calls_and_raises(self):
        fake = FakeGeminiClient(error=gemini.GeminiError("boom"))
        with self.assertRaises(gemini.GeminiError):
            fake.embed_query("x")
        self.assertEqual(fake.calls, [("embed_query", "x")])


if __name__ == "__main__":
    unittest.main()
