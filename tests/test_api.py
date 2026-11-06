"""실제 정제 데이터와 추천 엔진을 사용하는 API 통합 테스트.

프로젝트 루트에서: uv run python -m unittest discover -s tests -v
"""

import unittest

from fastapi.testclient import TestClient

from backend.genres import genre_mask
from backend.main import app
from backend.recommend_engine import df, mechanics

GENRE_KEYS = ["strategy", "family", "party", "thematic", "war", "childrens", "cgs", "deduction"]


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
            self.assertIsInstance(game["SharedMechanics"], list)
            self.assertIsInstance(game["SharedThemes"], list)
        # 다양성 재정렬(MMR)의 첫 번째 선택은 항상 최종 점수가 가장 높은 게임
        scores = [game["Score"] for game in games]
        self.assertEqual(scores[0], max(scores))

    def test_recommendation_explains_shared_mechanics(self):
        games = self.recommend().json()
        self.assertTrue(any(game["SharedMechanics"] for game in games))

    def test_recommendation_is_not_flooded_by_variants(self):
        # 예전 TF-IDF 방식은 Catan 추천 5개가 모두 Catan 변형판이었음
        names = [game["Name"].lower() for game in self.recommend().json()]
        self.assertLessEqual(sum("catan" in name for name in names), 1)

    def test_root_reports_active_signals(self):
        body = self.client.get("/").json()
        self.assertIn("mechanics", body["signals"])
        self.assertIsInstance(body["semantic_search"], bool)

    def test_semantic_search(self):
        if not self.client.get("/").json()["semantic_search"]:
            response = self.client.get(
                "/games/semantic-search", params={"query": "협력 게임"}
            )
            self.assertEqual(response.status_code, 503)
            self.skipTest("임베딩 미생성 또는 sentence-transformers 미설치")

        response = self.client.get(
            "/games/semantic-search",
            params={"query": "친구들과 함께 질병을 막는 협력 게임", "players": 4, "max_time": 60},
        )
        self.assertEqual(response.status_code, 200)
        games = response.json()
        self.assertTrue(0 < len(games) <= 10)
        for game in games:
            self.assertLessEqual(game["MinPlayers"], 4)
            self.assertGreaterEqual(game["MaxPlayers"], 4)
            self.assertLessEqual(game["ComMaxPlaytime"], 60)
        scores = [game["Score"] for game in games]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_semantic_search_rejects_invalid_input(self):
        for params in [{"query": "  "}, {"query": "co-op", "players": 0}, {"query": "co-op", "max_time": -1}]:
            with self.subTest(params=params):
                response = self.client.get("/games/semantic-search", params=params)
                self.assertEqual(response.status_code, 400)

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

    def test_search_includes_game_without_image(self):
        # 3-D Chess는 데이터에 이미지 주소가 없는 게임
        response = self.client.get("/games/search", params={"query": "3-D Chess"})
        self.assertEqual(response.status_code, 200)
        games = {game["Name"]: game for game in response.json()}
        self.assertEqual(games["3-D Chess"]["ImagePath"], "")   

    def test_game_detail_returns_full_info(self):
        response = self.client.get("/games/13")  # 13 = Catan
        self.assertEqual(response.status_code, 200)
        game = response.json()
        self.assertEqual(game["Name"], "Catan")
        # 검색 결과엔 없고 상세 조회에만 있는 항목 (영문 원문 문장 포함 확인)
        self.assertIn("Description", game)
        self.assertIn("In CATAN", game["Description"])
        self.assertIn("BestPlayers", game)

    def test_game_detail_unknown_id_is_not_found(self):
        response = self.client.get("/games/999999999") # 데이터에 없는 ID
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Game not found")

    def test_game_detail_rejects_non_numeric_id(self):
        response = self.client.get("/games/abc")
        self.assertEqual(response.status_code, 422)

    def test_search_still_works_after_detail_route(self):
        # /games/{bgg_id}가 /games/search를 가로채지 않는지 확인
        response = self.client.get("/games/search", params={"query": "Catan"})
        self.assertEqual(response.status_code, 200)

    def test_game_detail_without_image_returns_empty_image_path(self):
        response = self.client.get("/games/18422")  # Citadel: 이미지 주소 없음
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ImagePath"], "")

    def test_genres_lists_eight_genres_in_order(self):
        response = self.client.get("/genres")
        self.assertEqual(response.status_code, 200)
        genres = response.json()
        self.assertEqual([g["key"] for g in genres], GENRE_KEYS)
        self.assertEqual(genres[0]["label"], "전략")
        for genre in genres:
            self.assertTrue(genre["label"] and genre["description"])

    def test_genre_games_are_popular_sorted_and_limited(self):
        ratings_by_id = df.set_index("BGGId")["NumUserRatings"]
        for genre in self.client.get("/genres").json():
            with self.subTest(genre=genre["key"]):
                games = genre["games"]
                self.assertTrue(0 < len(games) <= 6)
                ratings = [g["BayesAvgRating"] for g in games]
                self.assertEqual(ratings, sorted(ratings, reverse=True))
                for game in games:
                    self.assertGreaterEqual(ratings_by_id[game["BGGId"]], 1000)

    def test_strategy_genre_includes_abstract_games(self):
        mask = genre_mask(df, mechanics, "strategy")
        abstract_only = ((df["Cat:Abstract"] == 1) & (df["Cat:Strategy"] == 0)).to_numpy()
        self.assertTrue(abstract_only.any())
        self.assertTrue(mask[abstract_only].all())

    def test_deduction_genre_uses_deduction_mechanic(self):
        col = list(mechanics.names).index("Deduction")
        expected = mechanics.binary[:, col].toarray().ravel() > 0
        self.assertTrue((genre_mask(df, mechanics, "deduction") == expected).all())

    def test_unknown_genre_key_is_rejected(self):
        with self.assertRaises(ValueError):
            genre_mask(df, mechanics, "no-such-genre")

    def test_genre_games_respect_conditions(self):
        response = self.client.get(
            "/genres/party/games", params={"players": 6, "max_time": 30}
        )
        self.assertEqual(response.status_code, 200)
        games = response.json()
        self.assertTrue(0 < len(games) <= 6)
        info = df.set_index("BGGId")
        party_ids = set(df.loc[genre_mask(df, mechanics, "party"), "BGGId"])
        for game in games:
            row = info.loc[game["BGGId"]]
            self.assertIn(game["BGGId"], party_ids)
            self.assertLessEqual(row["MinPlayers"], 6)
            self.assertGreaterEqual(row["MaxPlayers"], 6)
            self.assertLessEqual(row["ComMaxPlaytime"], 30)

    def test_genre_games_prefer_popular_then_rating(self):
        games = self.client.get(
            "/genres/family/games", params={"players": 2, "max_time": 30}
        ).json()
        self.assertEqual(len(games), 6)
        info = df.set_index("BGGId")
        for game in games:
            self.assertGreaterEqual(info.loc[game["BGGId"], "NumUserRatings"], 1000)
        ratings = [g["BayesAvgRating"] for g in games]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_genre_games_fill_with_less_popular_when_needed(self):
        # 워게임 4명 30분 이하는 리뷰 1000개 이상 게임이 4개뿐이라 나머지로 채움
        games = self.client.get(
            "/genres/war/games", params={"players": 4, "max_time": 30}
        ).json()
        self.assertEqual(len(games), 6)
        info = df.set_index("BGGId")
        popular = [info.loc[g["BGGId"], "NumUserRatings"] >= 1000 for g in games]
        self.assertIn(False, popular)
        # 인기 게임이 항상 앞에 옴
        self.assertEqual(popular, sorted(popular, reverse=True))

    def test_genre_games_work_without_conditions(self):
        response = self.client.get("/genres/strategy/games")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 6)

    def test_genre_games_unknown_genre_is_not_found(self):
        response = self.client.get("/genres/no-such-genre/games")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Genre not found")

    def test_genre_games_reject_invalid_values(self):
        for params in [{"players": 0}, {"max_time": 0}]:
            with self.subTest(params=params):
                response = self.client.get("/genres/family/games", params=params)
                self.assertEqual(response.status_code, 400)

    def test_genre_games_without_candidates_return_empty_list(self):
        response = self.client.get(
            "/genres/family/games", params={"players": 999999}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])    

if __name__ == "__main__":
    unittest.main()
