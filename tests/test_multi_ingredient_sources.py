
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import ddinter_lookup

class ClinicalPairDedupSourceTests(unittest.TestCase):
    def test_bactrim_warfarin_has_both_evidence_rows_but_one_pair_count(self):
        with tempfile.TemporaryDirectory() as dirname:
            file=Path(dirname)/'test-ddinter.sqlite3'
            with closing(sqlite3.connect(file)) as c, c:
                c.execute('CREATE TABLE drugs (id INTEGER PRIMARY KEY, name TEXT, norm TEXT)')
                c.execute('CREATE TABLE pairs (a INTEGER, b INTEGER, level TEXT)')
                c.executemany('INSERT INTO drugs VALUES (?, ?, ?)', [
                    (1,'Sulfamethoxazole','sulfamethoxazole'),
                    (2,'Trimethoprim','trimethoprim'),
                    (3,'Warfarin','warfarin')])
                c.execute('INSERT INTO pairs VALUES (1,3,\'Major\')')
            with (patch('ddinter_lookup.DB_PATH', file),
                  patch('ddinter_lookup.catalogue_ready',return_value=False)):
                report=ddinter_lookup.check_pairs(['Co-trimoxazole','warfarin'])
            self.assertEqual(report['status'],'ready')
            self.assertFalse(report['unrecognized'])
            self.assertEqual(report['safety_categories']['documented_interactions'],1)
            ingredient_pairs={(h['ingredient_a'].casefold(),h['ingredient_b'].casefold())
                              for h in report['alerts']}
            self.assertEqual(ingredient_pairs,{
                ('sulfamethoxazole','warfarin'),('trimethoprim','warfarin')})
            self.assertTrue(any(h['finding_type']=='documented_interaction'
                                and h['source_url'].startswith('https://') for h in report['alerts']))

if __name__=='__main__': unittest.main()
