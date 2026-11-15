import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import recommend_engine as eng, series


def idx_of(name: str) -> int:
    return int(eng.df.index[eng.df["Name"] == name][0])


def key(name: str):
    return series.KEYS[idx_of(name)]


def family_key_of_two_members(family: str):
    rows = eng.df[eng.df["Family"] == family].sort_values("NumUserRatings", ascending=False)
    # Lost Cities / Catan Card Game and Agricola / Le Havre share no name stem.
    names = rows["Name"].tolist()
    a, b = names[0], names[1]
    return key(a), key(b)


class SeriesKeysTest(unittest.TestCase):
    def test_family_groups_versions(self):
        self.assertEqual(
            key("Carcassonne"),
            key("Carcassonne: Hunters and Gatherers"),
        )
        self.assertEqual(key("Carcassonne"), key("New World: A Carcassonne Game"))
        self.assertEqual(key("Carcassonne"), key("Carcassonne: Star Wars"))
        self.assertEqual(key("Ticket to Ride"), key("Ticket to Ride: Europe"))
        self.assertEqual(key("Pandemic"), key("Pandemic Legacy: Season 1"))

    def test_publisher_line_family_does_not_group(self):
        for family in ("Two-player games (Kosmos)", "Harvest (Uwe Rosenberg)"):
            a, b = family_key_of_two_members(family)
            self.assertNotEqual(a, b, family)

    def test_name_prefix_joins_base_game(self):
        df = pd.DataFrame(
            {
                "BGGId": [1, 2, 3],
                "Name": ["Foo", "Foo: Big Box", "Star Wars: Bar"],
                "Family": ["", "", ""],
                "NumUserRatings": [2000, 1500, 1500],
            }
        )
        keys = series.series_keys(df, 1000)
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], keys[2])

    def test_base_games_join_series(self):
        df = pd.DataFrame(
            {
                "BGGId": [10, 20],
                "Name": ["Alpha", "Zeta Quest"],
                "Family": ["", ""],
                "NumUserRatings": [2000, 1500],
            }
        )
        keys = series.series_keys(df, 1000, base_games={20: "Alpha"})
        self.assertEqual(keys[0], keys[1])

    def test_unrelated_games_have_distinct_keys(self):
        self.assertNotEqual(key("Catan"), key("Pandemic"))


if __name__ == "__main__":
    unittest.main()
