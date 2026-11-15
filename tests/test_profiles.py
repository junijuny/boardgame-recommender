import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import build_profile_embeddings as bpe, gemini, profiles, recommend_engine as eng


class LoadTest(unittest.TestCase):
    def test_load_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(profiles.load(Path(d) / "none.json"), {})

    def test_load_broken_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text("{not json", encoding="utf-8")
            self.assertEqual(profiles.load(p), {})

    def test_load_reads_profiles(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.json"
            p.write_text(json.dumps({"model": "m", "profiles": {"7": {"profile": "x", "franchise": ["F"]}}}),
                         encoding="utf-8")
            got = profiles.load(p)
            self.assertEqual(got, {7: {"profile": "x", "franchise": ["F"]}})


class DocumentTest(unittest.TestCase):
    def test_document_contains_profile_tags_and_description(self):
        row = eng.df.index[eng.df["Name"] == "Pandemic"][0]
        bgg_id = int(eng.df.loc[row, "BGGId"])
        ids, docs = bpe.profile_documents({bgg_id: {"profile": "A tense race."}})
        self.assertEqual(ids.tolist(), [bgg_id])
        text = gemini.document_text(*docs[0])
        self.assertIn("title: Pandemic | text: A tense race. Mechanics:", text)
        self.assertIn("Themes:", text)


if __name__ == "__main__":
    unittest.main()
