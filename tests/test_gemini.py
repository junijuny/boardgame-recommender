import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import gemini
from backend.limits import DailyBudget
from tests.gemini_fake import FakeGeminiClient


class ExplainParsingTests(unittest.TestCase):
    def test_non_string_reasons_are_skipped(self):
        client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)
        client._generate = lambda *a, **k: {
            "reasons": [
                {"bgg_id": 1, "reason": None},
                {"bgg_id": 2, "reason": "Fine."},
            ]
        }
        self.assertEqual(client.explain("query", "x", None, []), {2: "Fine."})


class ExtractPromptTest(unittest.TestCase):
    def test_player_count_game_type_stays_in_search_text(self):
        text = gemini.EXTRACT_PROMPT
        self.assertIn("two-player game", text)
        self.assertIn("IS a gameplay aspect", text)
        self.assertIn("even when sort is popularity", text)
        self.assertIn("exact_players", text)

    def test_model_allocation(self):
        self.assertEqual(gemini.EXTRACT_MODEL, "gemini-3.8-flash")
        self.assertEqual(gemini.RERANK_MODEL, "gemini-3.8-flash")
        self.assertEqual(gemini.EXPLAIN_MODEL, "gemini-3.5-flash-lite")
        self.assertEqual(gemini.WEB_MODEL, "gemini-3.5-flash-lite")

    def test_thinking_level_uses_low_for_non_lite_models(self):
        from types import SimpleNamespace as NS

        client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)
        client._types = NS(ThinkingLevel=NS(MINIMAL="minimal", LOW="low"))
        self.assertEqual(client._thinking_level("gemini-3.8-flash"), "low")
        self.assertEqual(client._thinking_level("gemini-3.5-flash-lite"), "minimal")


class IntentParsingTest(unittest.TestCase):
    def test_null_and_string_fields_are_coerced(self):
        i = gemini._intent_from_dict({
            "search_text": None, "include_mechanics": "Dice Rolling",
            "exclude_themes": [1, None, "War"], "weight_min": None, "weight_max": 2,
        })
        self.assertEqual(i.search_text, "")
        self.assertEqual(i.include_mechanics, ("Dice Rolling",))
        self.assertEqual(i.exclude_themes, ("1", "War"))
        self.assertEqual((i.weight_min, i.weight_max), (None, 2.0))
        self.assertEqual(gemini._intent_from_dict({}).search_text, "")

    def test_web_query_parsed(self):
        self.assertEqual(gemini._intent_from_dict({"web_query": "South Korean board games"}).web_query,
                         "South Korean board games")
        self.assertEqual(gemini._intent_from_dict({"web_query": None}).web_query, "")
        self.assertEqual(gemini._intent_from_dict({}).web_query, "")

    def test_web_prompt_requires_searching(self):
        self.assertIn("Google Search before answering", gemini.WEB_PROMPT)
        self.assertIn("web_query", gemini.EXTRACT_PROMPT)

    def test_sort_is_parsed_and_unknown_values_fall_back_to_relevance(self):
        self.assertEqual(gemini._intent_from_dict({"sort": "popularity"}).sort, "popularity")
        self.assertEqual(gemini._intent_from_dict({"sort": " Rating "}).sort, "rating")
        self.assertEqual(gemini._intent_from_dict({"sort": "newest"}).sort, "newest")
        self.assertEqual(gemini._intent_from_dict({"sort": "cheapest"}).sort, "relevance")
        self.assertEqual(gemini._intent_from_dict({"sort": None}).sort, "relevance")
        self.assertEqual(gemini._intent_from_dict({}).sort, "relevance")

    def test_intent_from_dict_reads_new_fields(self):
        i = gemini._intent_from_dict({
            "age_max": 8, "categories": ["Family", "Party"], "low_text": True,
            "keywords": ["Star Wars"], "terms": ["zombies", "trains"], "exact_players": True,
        })
        self.assertEqual(i.age_max, 8.0)
        self.assertEqual(i.categories, ("Family", "Party"))
        self.assertIs(i.low_text, True)
        self.assertEqual(i.keywords, ("Star Wars",))
        self.assertEqual(i.terms, ("zombies", "trains"))
        self.assertIs(i.exact_players, True)
        d = gemini._intent_from_dict({})
        self.assertEqual(
            (d.age_max, d.categories, d.low_text, d.keywords, d.terms, d.exact_players),
            (None, (), False, (), (), False),
        )

    def test_bad_weight_raises_gemini_error(self):
        with self.assertRaises(gemini.GeminiError):
            gemini._intent_from_dict({"weight_min": "abc"})


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


class ProfilesParsingTest(unittest.TestCase):
    def test_profiles_parsing(self):
        client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)
        client._generate = lambda *a, **k: {
            "profiles": [
                {"bgg_id": 1, "profile": "A calm game.", "franchise": ["Foo"], "base_game": "Bar",
                 "designers": ["A B"], "designer_countries": ["Germany"]},
                {"bgg_id": 2, "franchise": [], "designers": []},
                {"bgg_id": 3, "profile": "Plain.", "base_game": ""},
            ]
        }
        out = client.write_profiles([{"bgg_id": 1}, {"bgg_id": 2}, {"bgg_id": 3}])
        self.assertEqual([p.bgg_id for p in out], [1, 3])
        self.assertEqual(out[0], gemini.GameProfile(
            bgg_id=1, profile="A calm game.", franchise=("Foo",), base_game="Bar",
            designers=("A B",), designer_countries=("Germany",)))
        self.assertIsNone(out[1].base_game)
        self.assertEqual(out[1].franchise, ())


class RerankParsingTest(unittest.TestCase):
    def _client(self, data):
        client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)
        client._generate = lambda *a, **k: data
        return client

    def test_rerank_result_parsing(self):
        out = self._client(
            {"interpretation": "Read as: x", "ranked_ids": [3, "4"], "weak_match": True}
        ).rerank("q", [])
        self.assertEqual(out, gemini.RerankResult("Read as: x", (3, 4), True))

    def test_missing_ids_raises(self):
        with self.assertRaises(gemini.GeminiError):
            self._client({"interpretation": "Read as: x", "weak_match": False}).rerank("q", [])

    def test_rerank_prompt_includes_filters_and_absurd_guard(self):
        seen = {}
        client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)

        def fake_generate(model, prompt, schema, max_tokens, timeout_seconds=10):
            seen["model"] = model
            seen["prompt"] = prompt
            return {"interpretation": "Read as: x", "ranked_ids": [], "weak_match": True}

        client._generate = fake_generate
        client.rerank("q", [], players=2, max_time=45)
        self.assertEqual(seen["model"], "gemini-3.8-flash")
        self.assertIn("Selected filters: 2 players, up to 45 min", seen["prompt"])
        self.assertIn("absurd, impossible", seen["prompt"])
        self.assertIn("specific subject or domain", seen["prompt"])

    def test_rerank_prompt_describes_time_slot(self):
        seen = {}
        client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)

        def fake_generate(model, prompt, schema, max_tokens, timeout_seconds=10):
            seen["prompt"] = prompt
            return {"interpretation": "Read as: x", "ranked_ids": [], "weak_match": False}

        client._generate = fake_generate
        client.rerank("q", [], players=2, max_time=60, min_time=30)
        self.assertIn("Selected filters: 2 players, 30-60 min", seen["prompt"])
        client.rerank("q", [], players=2, max_time=30, min_time=0)
        self.assertIn("Selected filters: 2 players, up to 30 min", seen["prompt"])
        # 상한 없는 마지막 칸 (2 hr or more)
        client.rerank("q", [], players=2, max_time=None, min_time=120)
        self.assertIn("Selected filters: 2 players, 120+ min", seen["prompt"])


def _web_client(resp, seen=None):
    from types import SimpleNamespace as NS

    client = gemini.GoogleGeminiClient.__new__(gemini.GoogleGeminiClient)
    client.usage = {"calls": 0, "prompt_tokens": 0, "output_tokens": 0}
    client._types = NS(
        Tool=lambda **k: k, GoogleSearch=lambda: None, ThinkingLevel=NS(MINIMAL=1),
        ThinkingConfig=lambda **k: k, HttpOptions=lambda **k: k,
        GenerateContentConfig=lambda **k: NS(**k),
    )

    def generate_content(**kw):
        if seen is not None:
            seen.update(kw)
        return resp

    client._client = NS(models=NS(generate_content=generate_content))
    return client


class WebAnswerParsingTest(unittest.TestCase):
    def test_web_answer_parsing(self):
        from types import SimpleNamespace as NS

        meta = NS(search_entry_point=NS(rendered_content="<div>sugg</div>"), web_search_queries=["a", "b"])
        resp = NS(text="Catan\n\nSummary.", candidates=[NS(grounding_metadata=meta)])
        seen = {}
        out = _web_client(resp, seen).web_search("q")
        self.assertEqual(out, gemini.WebAnswer("Catan\n\nSummary.", "<div>sugg</div>", 2))
        cfg = seen["config"]
        self.assertFalse(hasattr(cfg, "response_schema"))
        self.assertFalse(hasattr(cfg, "response_mime_type"))
        self.assertGreaterEqual(cfg.http_options["timeout"], 10_000)

    def test_missing_grounding_metadata_has_empty_html(self):
        from types import SimpleNamespace as NS

        resp = NS(text="x", candidates=[NS(grounding_metadata=None)])
        out = _web_client(resp).web_search("q")
        self.assertEqual((out.suggestions_html, out.search_count), ("", 0))


if __name__ == "__main__":
    unittest.main()
