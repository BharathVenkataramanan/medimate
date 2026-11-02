

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ddinter_lookup import check_pairs


class SelectedBrandIdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "fixture.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TABLE drugs (id INTEGER PRIMARY KEY, name TEXT, norm TEXT)")
            conn.execute("CREATE TABLE pairs (a INTEGER, b INTEGER, level TEXT)")
            conn.executemany(
                "INSERT INTO drugs VALUES (?, ?, ?)",
                [(1, "Acetaminophen", "acetaminophen"),
                 (2, "Oxycodone", "oxycodone"),
                 (3, "Amphetamine", "amphetamine"),
                 (4, "Dextroamphetamine", "dextroamphetamine")],
            )

    @staticmethod
    def catalog(name, rxcui=None):

        if name == "Percocet Pill" and rxcui in (None, "111"):
            return ["acetaminophen", "oxycodone"]
        return []

    def check(self, names, hints):
        with (patch("ddinter_lookup.DB_PATH", self.db),
              patch("ddinter_lookup.catalogue_ready", return_value=True),
              patch("ddinter_lookup.catalog_resolve", side_effect=self.catalog)):
            return check_pairs(names, rxnorm_ids=hints)

    def test_brand_only_rxnorm_id_does_not_hide_verified_adderall(self):
        result = self.check(["Percocet Pill", "Adderall"],
                            {"Percocet Pill": "111", "Adderall": "222"})
        self.assertEqual(result["unrecognized"], [])
        self.assertEqual(result["alerts"], [])
        pairs = {(x["ingredient_a"].casefold(), x["ingredient_b"].casefold())
                 for x in result["uncertain"]}
        self.assertEqual(pairs, {
            ("acetaminophen", "amphetamine"),
            ("acetaminophen", "dextroamphetamine"),
            ("oxycodone", "amphetamine"),
            ("oxycodone", "dextroamphetamine"),
        })
        self.assertTrue(all(x["reason"] == "no_documented_pair" for x in result["uncertain"]))

    def test_an_unknown_name_with_an_invalid_id_still_fails_closed(self):
        result = self.check(["Unverified Example", "Adderall"],
                            {"Unverified Example": "999", "Adderall": "222"})
        self.assertEqual(result["unrecognized"], ["Unverified Example"])

    def test_wrong_generic_id_cannot_fall_back_to_name_only(self):
        result = self.check(["acetaminophen", "Adderall"],
                            {"acetaminophen": "999", "Adderall": "222"})
        self.assertEqual(result["unrecognized"], ["acetaminophen"])


if __name__ == "__main__":
    unittest.main()
