"""실제 정제 데이터와 추천 엔진을 사용하는 API 통합 테스트.

프로젝트 루트에서: uv run python -m unittest discover -s tests -v
"""

import unittest

from fastapi.testclient import TestClient

from backend.main import app


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def recommend(self, **changes):
        payload = {"game_name": "Catan", "players": 4, "max_time": 90}
        payload.update(changes)
        return self.client.post("/recommend", json=payload)

    def test_root_reports_loaded_games(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["total_games"], 0)

    def test_search_trims_whitespace_and_ignores_case(self):
        response = self.client.get("/games/search", params={"query": " cAtAn "})
        self.assertEqual(response.status_code, 200)
        games = response.json()
        self.assertTrue(0 < len(games) <= 10)
        self.assertIn("Catan", [game["Name"] for game in games])
        for game in games:
            self.assertIn("catan", game["Name"].lower())
            self.assertEqual(set(game), {"BGGId", "Name", "YearPublished", "ImagePath"})

    def test_search_treats_brackets_as_literal_text(self):
        response = self.client.get("/games/search", params={"query": "["})
        self.assertEqual(response.status_code, 200)
        for game in response.json():
            self.assertIn("[", game["Name"])

    def test_search_without_matches_returns_empty_list(self):
        response = self.client.get(
            "/games/search", params={"query": "__no_such_boardgame_12345__"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_empty_search_is_bad_request(self):
        for query in ["", "   "]:
            with self.subTest(query=query):
                response = self.client.get("/games/search", params={"query": query})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["detail"], "Search query cannot be empty"
                )

    def test_missing_search_query_is_validation_error(self):
        self.assertEqual(self.client.get("/games/search").status_code, 422)

    def test_filter_respects_conditions_and_rating_order(self):
        response = self.client.get(
            "/games/filter", params={"players": 4, "max_time": 90}
        )
        self.assertEqual(response.status_code, 200)
        games = response.json()
        self.assertTrue(0 < len(games) <= 10)
        for game in games:
            self.assertLessEqual(game["MinPlayers"], 4)
            self.assertGreaterEqual(game["MaxPlayers"], 4)
            self.assertLessEqual(game["ComMaxPlaytime"], 90)
            self.assertGreaterEqual(game["BayesAvgRating"], 5.5)
        ratings = [game["BayesAvgRating"] for game in games]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_filter_without_matches_returns_empty_list(self):
        response = self.client.get(
            "/games/filter", params={"players": 999999, "max_time": 1}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_filter_rejects_nonpositive_conditions(self):
        for field in ["players", "max_time"]:
            for value in [0, -1]:
                with self.subTest(field=field, value=value):
                    params = {"players": 4, "max_time": 90, field: value}
                    response = self.client.get("/games/filter", params=params)
                    self.assertEqual(response.status_code, 400)

    def test_filter_rejects_invalid_types(self):
        response = self.client.get(
            "/games/filter", params={"players": "four", "max_time": 90}
        )
        self.assertEqual(response.status_code, 422)

    def test_recommendation_respects_conditions_and_ranking(self):
        response = self.recommend()
        self.assertEqual(response.status_code, 200)
        games = response.json()
        self.assertEqual(len(games), 5)
        self.assertEqual(len({game["BGGId"] for game in games}), 5)
        for game in games:
            self.assertNotEqual(game["Name"].strip().lower(), "catan")
            self.assertLessEqual(game["MinPlayers"], 4)
            self.assertGreaterEqual(game["MaxPlayers"], 4)
            self.assertLessEqual(game["ComMaxPlaytime"], 90)
            self.assertGreaterEqual(game["BayesAvgRating"], 5.5)
            self.assertGreaterEqual(game["Similarity"], 0)
            self.assertLessEqual(game["Similarity"], 1 + 1e-9)
        ranking = [(game["Similarity"], game["BayesAvgRating"]) for game in games]
        self.assertEqual(ranking, sorted(ranking, reverse=True))

    def test_recommendation_accepts_case_and_whitespace(self):
        response = self.recommend(game_name=" cAtAn ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.recommend().json())

    def test_unknown_game_is_not_found(self):
        response = self.recommend(game_name="__no_such_boardgame_12345__")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Game not found")

    def test_recommendation_without_candidates_is_not_found(self):
        response = self.recommend(players=999999, max_time=1)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"], "No games match the selected conditions"
        )

    def test_recommendation_rejects_invalid_values(self):
        changes = [
            {"game_name": "   "},
            {"players": 0},
            {"players": -1},
            {"max_time": 0},
            {"max_time": -1},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.recommend(**change).status_code, 400)

    def test_recommendation_rejects_invalid_request_schema(self):
        for payload in [{}, {"game_name": "Catan", "players": "four", "max_time": 90}]:
            with self.subTest(payload=payload):
                response = self.client.post("/recommend", json=payload)
                self.assertEqual(response.status_code, 422)

    def test_recommendation_requires_post(self):
        self.assertEqual(self.client.get("/recommend").status_code, 405)

    def test_cors_allows_local_frontend_preflight(self):
        for origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/recommend",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.headers["access-control-allow-origin"], origin
                )
                self.assertIn("POST", response.headers["access-control-allow-methods"])

    def test_cors_rejects_unlisted_origin_preflight(self):
        response = self.client.options(
            "/recommend",
            headers={
                "Origin": "https://unlisted.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_cors_headers_on_success_response(self):
        origin = "http://localhost:5173"
        response = self.client.post(
            "/recommend",
            headers={"Origin": origin},
            json={
                "game_name": "Catan",
                "players": 4,
                "max_time": 90,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_cors_headers_on_error_responses(self):
        origin = "http://localhost:5173"
        cases = [
            ({"game_name": "Catan", "players": 0, "max_time": 90}, 400),
            (
                {
                    "game_name": "__no_such_boardgame_12345__",
                    "players": 4,
                    "max_time": 90,
                },
                404,
            ),
            ({}, 422),
        ]
        for payload, status in cases:
            with self.subTest(status=status):
                response = self.client.post(
                    "/recommend", headers={"Origin": origin}, json=payload
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(
                    response.headers["access-control-allow-origin"], origin
                )

    def test_cors_omits_permission_header_for_unlisted_origin(self):
        response = self.client.get("/", headers={"Origin": "https://unlisted.example"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
