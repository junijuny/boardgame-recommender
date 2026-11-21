"""인기 차트(backend/charts.py, GET /charts) 테스트.

프로젝트 루트에서: uv run python -m unittest tests.test_charts -v
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.charts import CHART_GAME_COLUMNS, CHART_KEYS, build_charts, chart_games, load_chart_stats
from backend.recommend_engine import df


class ChartTests(unittest.TestCase):
    """차트 계산 함수 테스트 (서버 없이 실제 데이터로)"""

    @classmethod
    def setUpClass(cls):
        cls.stats = load_chart_stats(df)
        cls.charts = build_charts(df, cls.stats)

    def test_stats_rows_match_games(self):
        # df 와 행 순서·개수가 같아야 차트 숫자가 엉뚱한 게임에 붙지 않는다
        self.assertEqual(len(self.stats), len(df))
        self.assertFalse(self.stats.isna().any().any())

    def test_four_charts_in_order(self):
        self.assertEqual([c["key"] for c in self.charts], ["top", "most_owned", "most_wanted", "new"])
        for chart in self.charts:
            self.assertTrue(chart["label"])
            self.assertTrue(chart["description"])
            self.assertEqual(len(chart["games"]), 10)

    def test_game_fields(self):
        for chart in self.charts:
            for game in chart["games"]:
                self.assertEqual(set(game), set(CHART_GAME_COLUMNS))

    def test_json_serializable(self):
        # NaN 이 섞이면 JSON 변환에서 500 이 나므로 그대로 변환되는지 확인
        json.dumps(self.charts, allow_nan=False)

    def test_top_sorted_by_rank(self):
        ranks = [g["BggRank"] for g in chart_games(df, self.stats, "top")]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(ranks[0], 1)

    def test_most_owned_sorted(self):
        owned = [g["NumOwned"] for g in chart_games(df, self.stats, "most_owned")]
        self.assertEqual(owned, sorted(owned, reverse=True))

    def test_most_wanted_sorted(self):
        wished = [g["NumWish"] for g in chart_games(df, self.stats, "most_wanted")]
        self.assertEqual(wished, sorted(wished, reverse=True))

    def test_new_only_recent_popular_games(self):
        newest = int(df["YearPublished"].max())
        games = chart_games(df, self.stats, "new")
        ratings = [g["BayesAvgRating"] for g in games]
        self.assertEqual(ratings, sorted(ratings, reverse=True))
        for g in games:
            self.assertGreater(g["YearPublished"], newest - 3)
            self.assertGreaterEqual(g["NumUserRatings"], 1000)

    def test_limit(self):
        for key in CHART_KEYS:
            self.assertEqual(len(chart_games(df, self.stats, key, limit=3)), 3)

    def test_unknown_chart(self):
        with self.assertRaises(ValueError):
            chart_games(df, self.stats, "nope")


class ChartAPITests(unittest.TestCase):
    """GET /charts, GET /charts/{key} 응답 테스트"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from backend.main import app

        cls.client = TestClient(app)

    def test_list_charts(self):
        res = self.client.get("/charts")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([c["key"] for c in res.json()], CHART_KEYS)

    def test_one_chart(self):
        res = self.client.get("/charts/most_owned")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["key"], "most_owned")
        self.assertEqual(len(body["games"]), 10)

    def test_unknown_chart_404(self):
        res = self.client.get("/charts/nope")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"], "Chart not found")


if __name__ == "__main__":
    unittest.main()
