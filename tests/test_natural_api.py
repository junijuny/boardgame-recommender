import sys
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini, main, natural_search as ns
from backend.gemini import GeminiError, QueryIntent, set_client
from backend.limits import DailyBudget, RateLimiter
from tests.gemini_fake import FakeGeminiClient
from tests.test_natural_search import idx_of, make_index

client = TestClient(main.app)
BODY = {"query": "co-op", "players": 4, "max_time": 60}


class NaturalApiTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        self._budget = gemini.budget
        self._limiter = main.natural_limiter
        ns.clear_caches()
        e0 = np.zeros(8, dtype=np.float32)
        e0[0] = 1.0
        self.fake = FakeGeminiClient(
            intent=QueryIntent("co-op", include_mechanics=("Cooperative Game",)), query_vector=e0
        )
        set_client(self.fake)
        ns.set_index(make_index(idx_of("Pandemic")))
        main.natural_limiter = RateLimiter(10, 60)

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        gemini.budget = self._budget
        main.natural_limiter = self._limiter
        ns.clear_caches()

    def test_root_reports_flags(self):
        body = client.get("/").json()
        self.assertIsInstance(body["natural_search"], bool)
        self.assertIsInstance(body["explanations"], bool)
        self.assertTrue(body["explanations"])

    def test_explain_accepts_weak_match(self):
        r = client.post(
            "/explain", json={"mode": "query", "basis": "co-op", "game_ids": [1], "weak_match": True}
        )
        self.assertEqual(r.status_code, 200)

    def test_search_returns_five(self):
        r = client.post("/search/natural", json=BODY)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["games"]), 5)

    def test_search_returns_object(self):
        r = client.post("/search/natural", json=BODY)
        body = r.json()
        self.assertEqual(
            set(body),
            {"games", "interpretation", "weak_match", "web", "suggested_game", "redirect_to_game"},
        )
        self.assertEqual(body["interpretation"], "Read as: fake.")
        self.assertIs(body["weak_match"], False)
        self.assertIsNone(body["web"])
        self.assertIsNone(body["suggested_game"])
        self.assertIs(body["redirect_to_game"], False)

    def test_explicit_similar_query_redirects_without_gemini(self):
        r = client.post(
            "/search/natural", json={"query": "games like Catan", "players": 4, "max_time": 60}
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["redirect_to_game"])
        self.assertEqual(body["suggested_game"]["Name"], "Catan")
        self.assertEqual(body["games"], [])
        self.assertEqual(self.fake.calls, [])

    def test_exact_game_name_suggests_switch_without_redirect(self):
        r = client.post(
            "/search/natural", json={"query": "Catan", "players": 4, "max_time": 60}
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["redirect_to_game"])
        self.assertEqual(body["suggested_game"]["Name"], "Catan")
        self.assertEqual(len(body["games"]), 5)
        self.assertTrue(self.fake.calls)

    def test_rerank_failure_still_200(self):
        self.fake.rerank_error = GeminiError("boom")
        body = client.post("/search/natural", json=BODY).json()
        self.assertEqual(len(body["games"]), 5)
        self.assertIsNone(body["interpretation"])

    def test_validation(self):
        for q, p, t in [(" ", 4, 60), ("x" * 301, 4, 60), ("q", 0, 60), ("q", 4, 0)]:
            r = client.post("/search/natural", json={"query": q, "players": p, "max_time": t})
            self.assertEqual(r.status_code, 400, (q[:5], p, t))

    def test_unavailable_is_503(self):
        set_client(None)
        r = client.post("/search/natural", json=BODY)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"], "Natural language search is not available")

    def test_gemini_error_is_503(self):
        self.fake.error = GeminiError("boom")
        r = client.post("/search/natural", json=BODY)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"], "Natural language search is temporarily unavailable")

    def test_budget_exhausted_is_503(self):
        gemini.budget = DailyBudget(0)
        r = client.post("/search/natural", json=BODY)
        self.assertEqual(r.status_code, 503)

    def test_rate_limit_is_429(self):
        for _ in range(10):
            self.assertEqual(client.post("/search/natural", json=BODY).status_code, 200)
        r = client.post("/search/natural", json=BODY)
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()["detail"], "Too many requests")

    def test_existing_recommend_unaffected_without_key(self):
        set_client(None)
        r = client.post("/recommend", json={"game_name": "Catan", "players": 4, "max_time": 120})
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
