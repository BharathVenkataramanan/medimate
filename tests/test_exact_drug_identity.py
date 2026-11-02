


import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ddinter_lookup import check_pairs, resolve_ingredients


class ExactDdinterIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.temp.name) / 'synthetic_ddinter.sqlite3'
        drugs = (
            ('DDInter126', 'Asparaginase Erwinia chrysanthemi'),
            ('DDInter1355', 'Oxaliplatin'),
            ('DDInter370', 'Choline salicylate'),
            ('DDInter815', 'Gentamicin'),
            ('DDInter42', 'Alendronic acid'),
            ('DDInter490', 'Deferoxamine'),
            ('DDInter507', 'Desmopressin'),
            ('DDInter999', 'Mixed Example Product'),
        )
        pairs = (
            ('DDInter126', 'DDInter1355', 'Moderate'),
            ('DDInter370', 'DDInter815', 'Moderate'),
            ('DDInter42', 'DDInter490', 'Unknown'),
            ('DDInter42', 'DDInter507', 'Unknown'),
            ('DDInter999', 'DDInter490', 'Major'),
        )
        with closing(sqlite3.connect(cls.db)) as conn, conn:
            conn.execute('CREATE TABLE drugs (id TEXT PRIMARY KEY, name TEXT, norm TEXT)')
            conn.execute('CREATE TABLE pairs (a TEXT, b TEXT, level TEXT)')
            conn.executemany('INSERT INTO drugs VALUES (?, ?, ?)',
                             [(id_, name, name.casefold()) for id_, name in drugs])
            conn.executemany('INSERT INTO pairs VALUES (?, ?, ?)',
                             [(min(a, b), max(a, b), level) for a, b, level in pairs])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def fake_catalog(name, rxcui=None):


        mapping = {
            'Asparaginase Erwinia chrysanthemi': ['asparaginase'],
            'Oxaliplatin': ['oxaliplatin'],
            'Choline salicylate': ['choline'],
            'Gentamicin': ['gentamicin'],
            'Alendronic acid': ['alendronate'],
            'Deferoxamine': ['deferoxamine'],
            'Desmopressin': ['desmopressin'],
            'Mixed Example Product': ['choline', 'gentamicin'],
        }
        if rxcui is not None and rxcui != 'selected-rxcui':
            return []
        return mapping.get(name, [])

    def check(self, names, *, ids=None):
        with (patch('ddinter_lookup.DB_PATH', self.db),
              patch('ddinter_lookup.catalogue_ready', return_value=True),
              patch('ddinter_lookup.catalog_resolve', side_effect=self.fake_catalog)):
            return check_pairs(names, rxnorm_ids=ids)

    def test_observed_moderate_records_surface_as_severity_only(self):
        for first, second in (
            ('Asparaginase Erwinia chrysanthemi', 'Oxaliplatin'),
            ('Choline salicylate', 'Gentamicin'),
        ):
            with self.subTest(pair=(first, second)):
                result = self.check([first, second])
                self.assertEqual(result['unrecognized'], [])
                self.assertEqual(len(result['alerts']), 1)
                self.assertEqual(result['alerts'][0]['level'], 'Moderate')
                self.assertEqual(result['alerts'][0]['finding_type'],
                                 'ddinter_severity_only')
                self.assertEqual(result['uncertain'], [])

    def test_observed_unknown_records_surface_as_review_not_alert(self):
        for second in ('Deferoxamine', 'Desmopressin'):
            with self.subTest(second=second):
                result = self.check(['Alendronic acid', second])
                self.assertEqual(result['alerts'], [])
                self.assertEqual(len(result['uncertain']), 1)
                self.assertEqual(result['uncertain'][0]['reason'], 'level_unknown')
                self.assertEqual(result['uncertain'][0]['level'], 'Unknown')
                self.assertEqual(result['safety_categories']['needs_review'], 1)

    def test_selected_rxcui_keeps_verified_rxnorm_component(self):
        result = self.check(['Choline salicylate', 'Gentamicin'],
                            ids={'Choline salicylate': 'selected-rxcui'})
        self.assertEqual(result['alerts'], [])
        self.assertEqual(len(result['uncertain']), 1)
        self.assertEqual(result['uncertain'][0]['ingredient_a'], 'choline')
        self.assertEqual(result['uncertain'][0]['reason'], 'no_documented_pair')

    def test_multi_ingredient_rxnorm_product_is_never_collapsed_to_ddinter_name(self):
        result = self.check(['Mixed Example Product', 'Deferoxamine'])
        self.assertEqual(result['alerts'], [])
        self.assertEqual(len(result['uncertain']), 2)
        self.assertEqual({item['ingredient_a'] for item in result['uncertain']},
                         {'choline', 'Gentamicin'})

    def test_no_loose_alias_or_missing_ddinter_name_is_invented(self):
        with (closing(sqlite3.connect(self.db)) as conn,
              patch('ddinter_lookup.catalogue_ready', return_value=True),
              patch('ddinter_lookup.catalog_resolve', return_value=['choline'])):
            self.assertEqual(resolve_ingredients(conn, 'Choline salicylate 10 mg')
                             ['ingredients'], [{'id': None, 'generic': 'choline'}])
            self.assertEqual(resolve_ingredients(conn, 'Unrelated name')
                             ['ingredients'], [{'id': None, 'generic': 'choline'}])


if __name__ == '__main__':
    unittest.main()
