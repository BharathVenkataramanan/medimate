
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import medication_sources as src

class SearchPriorityTests(unittest.TestCase):
    def test_exact_nitroglycerin_first_when_db_has_many_formulations(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'ddinter.sqlite3'
            with closing(sqlite3.connect(db)) as con, con:
                con.execute('CREATE TABLE drugs (name TEXT, norm TEXT)')
                con.executemany('INSERT INTO drugs VALUES (?,?)', [(f'Nitroglycerin tablet {i}',f'nitroglycerin tablet {i}') for i in range(19)] + [('Nitroglycerin','nitroglycerin')])
            synthetic=[{'name':f'Nitroglycerin patch variation {i}','ingredient':'Nitroglycerin','source':'NLM RxNorm · mapped components','rxcui':str(i)} for i in range(8)]
            with patch.object(src,'DB_PATH',db), patch.object(src,'catalog_search',return_value=synthetic):
                report=src.suggestions_local('nitroglycerin')
            self.assertEqual(report['status'],'ready')
            self.assertEqual(report['matches'][0]['name'],'Nitroglycerin')
            self.assertEqual(len(report['matches']),9)
    def test_no_invented_exact_if_only_formulations_exist(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'ddinter.sqlite3'
            with closing(sqlite3.connect(db)) as con, con:
                con.execute('CREATE TABLE drugs (name TEXT, norm TEXT)')
                con.execute('INSERT INTO drugs VALUES (?,?)',('ExampleDrug tablets','exampledrug tablets'))
            with patch.object(src,'DB_PATH',db),patch.object(src,'catalog_search',return_value=[]):
                report=src.suggestions_local('exampledrug')
            self.assertEqual(report['matches'][0]['name'],'ExampleDrug tablets')
            self.assertNotIn('ExampleDrug',[x['name'] for x in report['matches']])

if __name__=='__main__': unittest.main()
