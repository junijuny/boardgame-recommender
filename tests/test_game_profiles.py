import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import build_game_profiles as bgp
from backend import gemini, recommend_engine
from tests.gemini_fake import FakeGeminiClient

WORDS = " ".join(["word"] * 60)


def profile(**kw) -> gemini.GameProfile:
    base = dict(bgg_id=1, profile=WORDS, franchise=(), base_game=None, designers=(), designer_countries=())
    base.update(kw)
    return gemini.GameProfile(**base)


class ProfileInputTest(unittest.TestCase):
    def test_profile_input_fields(self):
        d = bgp.profile_input(0)
        for key in ("bgg_id", "name", "year", "mechanics", "themes", "categories", "weight",
                    "age", "players", "playtime", "description", "include_designers"):
            self.assertIn(key, d)
        self.assertLessEqual(len(d["description"]), 800)

    def test_include_designers_follows_review_count(self):
        df = recommend_engine.df
        hi = int(df.index[df["NumUserRatings"] >= bgp.DESIGNER_MIN_REVIEWS][0])
        lo = int(df.index[df["NumUserRatings"] < bgp.DESIGNER_MIN_REVIEWS][0])
        self.assertTrue(bgp.profile_input(hi)["include_designers"])
        self.assertFalse(bgp.profile_input(lo)["include_designers"])


class CleanProfileTest(unittest.TestCase):
    def test_clean_profile_rules(self):
        self.assertIsNone(bgp.clean_profile(profile(profile="한글 " + WORDS)))
        self.assertIsNone(bgp.clean_profile(profile(profile="one two three four five six seven eight nine ten")))
        self.assertIsNone(bgp.clean_profile(profile(profile=" ".join(["w"] * 201))))
        cleaned = bgp.clean_profile(profile(designers=tuple(f"D{i}" for i in range(8)),
                                            franchise=("x" * 100,)))
        self.assertEqual(len(cleaned.designers), 5)
        self.assertEqual(cleaned.franchise, ("x" * 60,))
        same = bgp.clean_profile(profile(base_game="Own Name"), name="own name")
        self.assertIsNone(same.base_game)
        self.assertEqual(bgp.clean_profile(profile(base_game="Other"), name="X").base_game, "Other")


class CleanRulesAC(unittest.TestCase):
    def test_own_name_franchise_dropped(self):
        p = profile(franchise=("CATAN", "Star Wars", "catan!"))
        self.assertEqual(bgp.clean_profile(p, name="Catan").franchise, ("Star Wars",))
        self.assertEqual(bgp.clean_profile(profile(franchise=("Pandemic",)), name="Pandemic Legacy").franchise, ("Pandemic",))

    def test_designers_dropped_when_not_included(self):
        p = profile(designers=("A",), designer_countries=("Germany",))
        c = bgp.clean_profile(p, name="X", include_designers=False)
        self.assertEqual((c.designers, c.designer_countries), ((), ()))
        c = bgp.clean_profile(p, name="X")
        self.assertEqual(c.designers, ("A",))

    def test_prompt_asks_60_to_90_words_and_designer_flag(self):
        self.assertIn("60-90 words", gemini.PROFILE_PROMPT)
        self.assertIn("include_designers", gemini.PROFILE_PROMPT)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.ids = [int(i) for i in recommend_engine.df["BGGId"].head(3)]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "p.json"

    def test_build_resumes(self):
        fake = FakeGeminiClient()
        bgp.build(self.ids, self.out, batch=10, limit=2, client=fake)
        self.assertEqual(len(json.loads(self.out.read_text("utf-8"))["profiles"]), 2)
        fake2 = FakeGeminiClient()
        bgp.build(self.ids, self.out, batch=10, client=fake2)
        data = json.loads(self.out.read_text("utf-8"))
        self.assertEqual(len(data["profiles"]), 3)
        self.assertIn("model", data)
        self.assertIn("created", data)
        self.assertEqual(len(fake2.calls), 1)
        sent = [g["bgg_id"] for g in fake2.calls[0][1]]
        self.assertEqual(sent, [self.ids[2]])

    def test_build_enforces_designer_cutoff(self):
        df = recommend_engine.df
        lo = int(df["BGGId"][df["NumUserRatings"] < bgp.DESIGNER_MIN_REVIEWS].iloc[0])
        bgp.build([lo], self.out, client=FakeGeminiClient())
        rec = json.loads(self.out.read_text("utf-8"))["profiles"][str(lo)]
        self.assertEqual((rec["designers"], rec["designer_countries"]), ([], []))

    def test_build_skips_bad_batch_items(self):
        fake = FakeGeminiClient(extra_profiles=[profile(bgg_id=999999999)])
        bgp.build(self.ids[:1], self.out, client=fake)
        data = json.loads(self.out.read_text("utf-8"))
        self.assertEqual(list(data["profiles"]), [str(self.ids[0])])


if __name__ == "__main__":
    unittest.main()
