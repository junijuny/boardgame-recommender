import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import explain, gemini, main, natural_search as ns
from backend.gemini import GeminiError, set_client
from backend.limits import RateLimiter
from backend.recommend_engine import df
from tests.gemini_fake import FakeGeminiClient

client = TestClient(main.app)

A, B, C, D = [int(x) for x in df["BGGId"].iloc[:4]]


def post(body):
    return client.post("/explain", json=body)


def explain_calls(fake):
    return [c for c in fake.calls if c[0] == "explain"]


class ExplainTest(unittest.TestCase):
    def setUp(self):
        self._client = gemini._client
        self._index = ns._index
        self._limiter = main.explain_limiter
        explain.clear_cache()
        self.fake = FakeGeminiClient(reasons={})
        set_client(self.fake)
        main.explain_limiter = RateLimiter(30, 60)

    def tearDown(self):
        gemini._client = self._client
        ns._index = self._index
        main.explain_limiter = self._limiter
        explain.clear_cache()

    def req(self, game_ids, mode="query", basis="co-op games"):
        return {"mode": mode, "basis": basis, "game_ids": game_ids}

    def test_returns_reasons_for_requested_ids(self):
        self.fake.reasons = {A: "A trading game with a modular board, like Catan."}
        r = post({"mode": "similar", "basis": "Catan", "game_ids": [A]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json()["reasons"], {str(A): "A trading game with a modular board, like Catan."}
        )
        call = self.fake.calls[0]
        self.assertEqual(call[1], "similar")
        self.assertEqual(call[3]["name"], "Catan")
        self.assertEqual([g["bgg_id"] for g in call[4]], [A])

    def test_drops_hangul_empty_and_unrequested(self):
        self.fake.reasons = {A: "협력 게임입니다.", B: "  ", C: " Fine sentence. ", 999999999: "Extra."}
        r = post(self.req([A, B, C]))
        self.assertEqual(r.json()["reasons"], {str(C): "Fine sentence."})

    def test_cache_avoids_second_call(self):
        self.fake.reasons = {A: "One."}
        post(self.req([A]))
        r = post(self.req([A]))
        self.assertEqual(r.json()["reasons"], {str(A): "One."})
        self.assertEqual(len(explain_calls(self.fake)), 1)

    def test_only_uncached_ids_sent_in_order(self):
        self.fake.reasons = {A: "One.", B: "Two.", C: "Three."}
        post(self.req([A]))
        post(self.req([C, A, B, C]))
        self.assertEqual([g["bgg_id"] for g in explain_calls(self.fake)[-1][4]], [C, B])

    def test_unknown_ids_ignored(self):
        r = post(self.req([999999999, A]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([g["bgg_id"] for g in self.fake.calls[0][4]], [A])

    def test_unknown_basis_game_is_404(self):
        r = post({"mode": "similar", "basis": "No Such Game", "game_ids": [A]})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "Game not found")

    def test_validation(self):
        for body in [
            self.req([A], basis=" "),
            self.req([A], basis="x" * 301),
            self.req([]),
            self.req(list(range(1, 12))),
        ]:
            self.assertEqual(post(body).status_code, 400)

    def test_no_client_is_503(self):
        set_client(None)
        r = post(self.req([A]))
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"], "Explanations are not available")

    def test_gemini_error_is_503(self):
        self.fake.error = GeminiError("boom")
        r = post(self.req([A]))
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"], "Explanations are temporarily unavailable")

    def test_rate_limit_is_429(self):
        for _ in range(30):
            self.assertEqual(post(self.req([A])).status_code, 200)
        self.assertEqual(post(self.req([A])).status_code, 429)

    def test_explanations_work_without_index(self):
        ns.set_index(None)
        self.fake.reasons = {A: "Fine."}
        self.assertEqual(post(self.req([A])).status_code, 200)

    def test_game_facts_shape(self):
        facts = explain.game_facts(0)
        self.assertEqual(
            set(facts),
            {"bgg_id", "name", "year", "players", "playtime", "weight", "mechanics", "themes", "description"},
        )
        self.assertLessEqual(len(facts["description"]), 600)
        self.assertIsInstance(facts["mechanics"], list)


if __name__ == "__main__":
    unittest.main()
