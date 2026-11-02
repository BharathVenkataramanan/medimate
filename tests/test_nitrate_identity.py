
from __future__ import annotations
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ddinter_lookup import check_pairs
from verified_medicines import RULE_INDEX


class NitrateIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'ddinter.sqlite3'
        with closing(sqlite3.connect(self.db)) as conn,conn:
            conn.execute('CREATE TABLE drugs (id INTEGER PRIMARY KEY,name TEXT,norm TEXT)')
            conn.execute('CREATE TABLE pairs (a INTEGER,b INTEGER,level TEXT)')
            conn.executemany('INSERT INTO drugs VALUES(?,?,?)', [
                (1,'tadalafil','tadalafil'),(2,'isosorbide','isosorbide'),
                (3,'isosorbide mononitrate','isosorbide mononitrate'),
                (4,'isosorbide dinitrate','isosorbide dinitrate'),
                (5,'sildenafil','sildenafil'),(6,'unrelated','unrelated')])

    @staticmethod
    def fake_catalog(name,rxcui=None):
        if rxcui is not None and rxcui not in ('28004','317110'):
            return []
        if 'isosorbide mononitrate' in name.casefold() or 'isosorbide dinitrate' in name.casefold():
            return ['isosorbide']
        if name.casefold()=='ambiguous isosorbide brand':
            return ['isosorbide']
        if name.casefold()=='multiingredient isosorbide product':
            return ['isosorbide','unrelated']
        return [name.casefold()]

    def check(self,names,ids=None):
        with (patch('ddinter_lookup.DB_PATH',self.db),
              patch('ddinter_lookup.catalogue_ready',return_value=True),
              patch('ddinter_lookup.catalog_resolve',side_effect=self.fake_catalog)):
            return check_pairs(names,rxnorm_ids=ids)

    def assert_specific_alert(self,result,ingredient):
        self.assertEqual(result['unrecognized'],[])
        expected=RULE_INDEX[frozenset(('tadalafil',ingredient))]
        matching=[a for a in result['alerts']
                  if a['finding_type']=='documented_interaction'
                  and {a['ingredient_a'].casefold(),a['ingredient_b'].casefold()}=={'tadalafil',ingredient}]
        self.assertEqual(len(matching),1,result)
        self.assertEqual(matching[0]['level'],'Contraindicated')
        self.assertEqual(matching[0]['source_url'],expected['source_url'])
        self.assertTrue(matching[0]['effects'])

    def test_precise_name_not_lost_by_rxnorm_base_ingredient(self):
        self.assert_specific_alert(self.check(['tadalafil','isosorbide mononitrate']),
                                   'isosorbide mononitrate')

    def test_verified_5_mononitrate_synonym_retains_form(self):
        with patch('test_nitrate_identity.NitrateIdentityTests.fake_catalog', side_effect=lambda name,rxcui=None: ['isosorbide 5-mononitrate'] if name=='isosorbide mononitrate' else [name.casefold()]):
            self.assert_specific_alert(self.check(['tadalafil','isosorbide mononitrate']), 'isosorbide mononitrate')

    def test_dinitrate_identity_is_also_preserved(self):
        self.assert_specific_alert(self.check(['tadalafil','isosorbide dinitrate']),
                                   'isosorbide dinitrate')

    def test_selected_verified_product_retains_precise_identity(self):
        name='24 HR isosorbide mononitrate 30 MG Extended Release Oral Tablet'
        self.assert_specific_alert(self.check(['tadalafil',name],{name:'317110'}),
                                   'isosorbide mononitrate')

    def test_ambiguous_isosorbide_is_not_assumed_to_be_a_nitrate(self):
        for name in ('isosorbide','ambiguous isosorbide brand',
                     'multiingredient isosorbide product'):
            with self.subTest(name=name):
                result=self.check(['tadalafil',name])
                self.assertFalse(result['alerts'],result)

    def test_unverified_selected_rxcui_does_not_fall_back_to_a_name(self):
        result=self.check(['tadalafil','isosorbide mononitrate'],
                          {'isosorbide mononitrate':'999999'})
        self.assertFalse(result['alerts'])
        self.assertIn('isosorbide mononitrate',result['unrecognized'])

    def test_exact_checked_form_surfaces_without_ddinter_nitrate_row(self):
        with closing(sqlite3.connect(self.db)) as conn,conn:
            conn.execute('DELETE FROM drugs WHERE norm=?',('isosorbide mononitrate',))
        self.assert_specific_alert(self.check(['tadalafil','isosorbide mononitrate']),
                                   'isosorbide mononitrate')

    def test_brand_name_containing_nitrate_phrase_is_not_automatically_resolved(self):
        result=self.check(['tadalafil','Imaginary isosorbide mononitrate product'])
        self.assertFalse(result['alerts'])
        self.assertTrue(result['uncertain'])

if __name__=='__main__':
    unittest.main()
