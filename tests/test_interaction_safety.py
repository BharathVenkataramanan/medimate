


import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ddinter_lookup import check_pairs, safety_categories
from verified_medicines import RULE_INDEX


class InteractionSafety71Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.db = Path(cls.directory.name) / "synthetic_ddinter.sqlite3"
        ingredients = sorted({ingredient for rule in RULE_INDEX.values()
                              for ingredient in (rule["a"], rule["b"])} |
                             {"acetaminophen", "orphenadrine", "amphetamine",
                              "dextroamphetamine", "fixture-a", "fixture-b",
                              "fixture-c", "fixture-d", "fixture-e"})
        cls.ids = {name: index for index, name in enumerate(ingredients, 1)}
        with closing(sqlite3.connect(cls.db)) as conn, conn:
            conn.execute("CREATE TABLE drugs (id INTEGER PRIMARY KEY, name TEXT, norm TEXT)")
            conn.execute("CREATE TABLE pairs (a INTEGER, b INTEGER, level TEXT)")
            conn.executemany("INSERT INTO drugs VALUES (?, ?, ?)",
                             [(index, name.title(), name) for name, index in cls.ids.items()])
            for first, second, level in [
                ("fixture-a", "fixture-b", "Major"),
                ("fixture-a", "fixture-c", "Moderate"),
                ("fixture-a", "fixture-d", "Minor"),
                ("fixture-a", "fixture-e", "Unknown"),
            ]:
                left, right = sorted([cls.ids[first], cls.ids[second]])
                conn.execute("INSERT INTO pairs VALUES (?, ?, ?)", (left, right, level))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    @staticmethod
    def fake_catalog(name, rxcui=None):
        if name == "Percocet Pill" and rxcui in (None, "111"):
            return ["acetaminophen", "oxycodone"]
        return []

    def check(self, names, ids=None):
        with (patch("ddinter_lookup.DB_PATH", self.db),
              patch("ddinter_lookup.catalogue_ready", return_value=True),
              patch("ddinter_lookup.catalog_resolve", side_effect=self.fake_catalog)):
            return check_pairs(names, rxnorm_ids=ids)

    def test_all_source_linked_ingredient_rules_are_documented(self):


        self.assertGreaterEqual(len(RULE_INDEX), 60)
        for rule in RULE_INDEX.values():
            with self.subTest(pair=(rule["a"], rule["b"])):
                report = self.check([rule["a"], rule["b"]])
                self.assertEqual(report["unrecognized"], [])
                self.assertEqual(len(report["alerts"]), 1)
                self.assertEqual(report["alerts"][0]["level"], rule["level"])
                self.assertEqual(report["safety_categories"]["documented_interactions"], 1)
                self.assertEqual(report["safety_categories"]["needs_review"], 0)
                self.assertFalse(report["safety_categories"]["no_documented_interactions"])

    def test_percocet_and_adderall_are_recognized_but_not_falsely_cleared(self):
        report = self.check(["Percocet Pill", "Adderall"],
                            {"Percocet Pill": "111", "Adderall": "222"})
        self.assertEqual(report["unrecognized"], [])
        self.assertEqual(report["alerts"], [])
        self.assertEqual(len(report["uncertain"]), 4)
        self.assertEqual({(r["ingredient_a"].casefold(), r["ingredient_b"].casefold())
                          for r in report["uncertain"]}, {
            ("acetaminophen", "amphetamine"),
            ("acetaminophen", "dextroamphetamine"),
            ("oxycodone", "amphetamine"),
            ("oxycodone", "dextroamphetamine"),
        })
        self.assertEqual(report["safety_categories"]["needs_review"], 1)
        self.assertFalse(report["safety_categories"]["no_documented_interactions"])

    def test_percocet_with_valium_has_both_documented_and_incomplete_evidence(self):
        report = self.check(["Percocet Pill", "Valium"], {"Percocet Pill": "111"})
        self.assertEqual(len(report["alerts"]), 1)
        self.assertEqual(report["alerts"][0]["finding_type"], "documented_interaction")
        self.assertEqual(report["alerts"][0]["ingredient_a"].casefold(), "oxycodone")
        self.assertEqual(len(report["uncertain"]), 1)
        self.assertEqual(report["safety_categories"]["documented_interactions"], 1)
        self.assertEqual(report["safety_categories"]["needs_review"], 1)

    def test_duplicate_paracetamol_is_separate_from_unconfirmed_comparison(self):
        report = self.check(["Anarex", "Panadol"])
        self.assertEqual(report["unrecognized"], [])
        self.assertEqual(len(report["alerts"]), 1)
        self.assertEqual(report["alerts"][0]["finding_type"], "duplicate_ingredient")
        self.assertEqual(report["safety_categories"]["documented_interactions"], 0)
        self.assertEqual(report["safety_categories"]["duplicate_ingredients"], 1)
        self.assertEqual(report["safety_categories"]["needs_review"], 1)

    def test_unknown_name_is_not_silently_suppressed(self):
        report = self.check(["Some Unverified Pill", "Adderall"])
        self.assertEqual(report["unrecognized"], ["Some Unverified Pill"])
        self.assertEqual(report["safety_categories"]["unrecognized_medicines"], 1)
        self.assertFalse(report["safety_categories"]["no_documented_interactions"])

    def test_unverified_rxcui_mismatch_fails_closed(self):
        report = self.check(["fixture-a", "Adderall"], {"fixture-a": "999"})
        self.assertEqual(report["unrecognized"], ["fixture-a"])

    def test_synthetic_ddinter_levels_are_categorized_by_evidence(self):

        for second, level in [("fixture-b", "Major"), ("fixture-c", "Moderate"),
                              ("fixture-d", "Minor")]:
            with self.subTest(level=level):
                report = self.check(["fixture-a", second])
                self.assertEqual(report["alerts"][0]["finding_type"], "ddinter_severity_only")
                self.assertEqual(report["alerts"][0]["level"], level)
                self.assertEqual(report["safety_categories"]["documented_interactions"], 1)
        unknown = self.check(["fixture-a", "fixture-e"])
        self.assertEqual(unknown["alerts"], [])
        self.assertEqual(unknown["uncertain"][0]["reason"], "level_unknown")
        self.assertEqual(unknown["safety_categories"]["needs_review"], 1)

    def test_missing_db_returns_unavailable_without_touching_any_records(self):
        with patch("ddinter_lookup.DB_PATH", self.db.parent / "missing.sqlite3"):
            report = check_pairs(["Adderall", "Percocet Pill"])
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["safety_categories"])

    def test_summary_counts_distinct_medicine_pairs_not_ingredient_rows(self):
        summary = safety_categories(
            [{"finding_type": "documented_interaction"},
             {"finding_type": "duplicate_ingredient"}],
            [{"first": "a", "second": "b"}, {"first": "a", "second": "b"},
             {"first": "a", "second": "c"}], ["unknown"])
        self.assertEqual(summary, {
            "documented_interactions": 1, "duplicate_ingredients": 1,
            "needs_review": 2, "unrecognized_medicines": 1,
            "no_documented_interactions": False,
        })

    def test_empty_summary_does_not_claim_checked_pairs_safe(self):
        summary = safety_categories([], [], [])
        self.assertTrue(summary["no_documented_interactions"])
        self.assertEqual(summary["needs_review"], 0)


if __name__ == "__main__":
    unittest.main()
