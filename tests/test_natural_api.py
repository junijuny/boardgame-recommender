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

    def test_search_returns_five(self):
        r = client.post("/search/natural", json=BODY)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 5)

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
