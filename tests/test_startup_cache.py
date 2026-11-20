"""시작 캐시(features.load_startup_data) 테스트.

캐시에서 읽은 결과가 CSV에서 새로 만든 결과와 같은지, 캐시가 오래됐거나 깨졌을 때
CSV에서 다시 만드는지 확인한다. 실제 data/ 폴더는 건드리지 않고 임시 폴더에 캐시를 만든다.

프로젝트 루트에서: uv run python -m unittest tests.test_startup_cache -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import features


def same_features(a: features.BinaryFeatures, b: features.BinaryFeatures) -> bool:
    return (
        list(a.names) == list(b.names)
        and (a.binary != b.binary).nnz == 0
        and (a.weighted != b.weighted).nnz == 0
        and (a.idf == b.idf).all()
    )


class StartupCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 비교 기준: 캐시 없이 CSV에서 바로 만든 결과
        cls.df = features.load_games()
        cls.mechanics = features.load_binary_features(features.MECHANICS_PATH, cls.df["BGGId"])
        cls.themes = features.load_binary_features(features.THEMES_PATH, cls.df["BGGId"])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "startup_cache.pkl"

    def tearDown(self):
        self.tmp.cleanup()

    def assert_same_as_csv(self, result):
        df, mechanics, themes = result
        self.assertTrue(df.equals(self.df))
        self.assertTrue(same_features(mechanics, self.mechanics))
        self.assertTrue(same_features(themes, self.themes))

    def test_first_call_creates_cache(self):
        self.assertFalse(self.cache.exists())
        result = features.load_startup_data(self.cache)
        self.assertTrue(self.cache.exists())
        self.assert_same_as_csv(result)

    def test_second_call_reads_cache_with_same_result(self):
        features.load_startup_data(self.cache)
        result = features.load_startup_data(self.cache)
        self.assert_same_as_csv(result)
        self.assertIsInstance(result[1], features.BinaryFeatures)

    def test_stale_cache_is_rebuilt(self):
        features.load_startup_data(self.cache)
        # 캐시 수정 시각을 원본 CSV보다 옛날로 바꿔서 "오래된 캐시" 상황을 만든다
        old = min(p.stat().st_mtime for p in features.STARTUP_SOURCES) - 100
        os.utime(self.cache, (old, old))
        result = features.load_startup_data(self.cache)
        self.assert_same_as_csv(result)
        self.assertGreater(self.cache.stat().st_mtime, old)

    def test_broken_cache_falls_back_to_csv(self):
        self.cache.write_bytes(b"not a pickle")
        result = features.load_startup_data(self.cache)
        self.assert_same_as_csv(result)

    def test_code_change_rebuilds_cache(self):
        # load_games() 같은 캐시 내용을 만드는 코드만 바뀌어도 (CSV는 그대로) 캐시를 다시 만들어야 한다
        sources = [p.resolve() for p in features.STARTUP_SOURCES]
        self.assertIn(Path(features.__file__).resolve(), sources)

    def test_failed_save_leaves_no_temp_file(self):
        with mock.patch.object(features.pickle, "dump", side_effect=OSError("disk full")):
            result = features.load_startup_data(self.cache)
        self.assert_same_as_csv(result)  # 저장에 실패해도 CSV 결과는 그대로 돌려준다
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])  # 캐시도 임시 파일도 남지 않음


if __name__ == "__main__":
    unittest.main()
