
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import audit_critical_interactions as auditmod
from ddinter_lookup import check_pairs
from verified_medicines import RULE_INDEX


class ClinicalReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/'ddinter_test.sqlite3'
        ingredients=sorted({v for a,b,_ in auditmod.CRITICAL_CASES for v in (a,b)} |
                           {'acetaminophen','oxycodone','ibuprofen','orphenadrine','sulfamethoxazole'})
        with closing(sqlite3.connect(cls.path)) as con,con:
            con.execute('CREATE TABLE drugs (id INTEGER PRIMARY KEY,name TEXT,norm TEXT)')
            con.execute('CREATE TABLE pairs (a INTEGER,b INTEGER,level TEXT)')
            con.executemany('INSERT INTO drugs VALUES (?, ?, ?)',
                            [(i,ingredient,ingredient) for i,ingredient in enumerate(ingredients,1)])
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self,names):
        with (patch('ddinter_lookup.DB_PATH',self.path),
              patch('ddinter_lookup.catalogue_ready',return_value=False)):
            return check_pairs(names)

    def test_all_critical_cases_have_original_source_and_surfaced_warning(self):
        for first,second,_ in auditmod.CRITICAL_CASES:
            with self.subTest(first=first,second=second):
                rule=RULE_INDEX.get(frozenset((first,second)))
                self.assertIsNotNone(rule)
                self.assertTrue(rule['source_url'].startswith('https://'))
                result=self.check([first,second])
                self.assertEqual(result['unrecognized'], [])
                self.assertTrue(any(a['finding_type']=='documented_interaction' and
                                    a['source_url']==rule['source_url'] for a in result['alerts']))
                self.assertEqual(result['safety_categories']['documented_interactions'],1)

    def test_audit_scores_each_case_without_internet(self):
        rows=auditmod.check_reference_cases(checker=self.check)
        self.assertEqual(len(rows),len(auditmod.CRITICAL_CASES)+len(auditmod.PRODUCT_CASES))
        self.assertTrue(all(r['outcome']=='pass' for r in rows),rows)

    def test_combo_aliases_are_exact_and_source_linked(self):
        from rxnorm_catalog import known_brand
        for product,other,ingredient,comparator,_ in auditmod.PRODUCT_CASES:
            with self.subTest(product=product):
                self.assertEqual(known_brand(product)['ingredients'],
                                 ['sulfamethoxazole','trimethoprim'])
                result=self.check([product,other])
                self.assertFalse(result['unrecognized'])
                self.assertTrue(any(a.get('finding_type')=='documented_interaction'
                                    for a in result['alerts']))
                compared={str(a.get(field,'')).casefold()
                          for a in result['alerts']+result['uncertain']
                          for field in ('ingredient_a','ingredient_b')}
                self.assertTrue({'trimethoprim','sulfamethoxazole'} <= compared)
        self.assertIsNone(known_brand('SomeBactrimLikeBrand'))

    def test_unknown_medicine_does_not_trigger_fictitious_rule(self):
        result=self.check(['Imaginary Medicine ABC123', 'warfarin'])
        self.assertFalse(result['alerts'])
        self.assertIn('Imaginary Medicine ABC123',result['unrecognized'])

    def test_absent_pair_does_not_prove_safety_or_notify(self):
        result=self.check(['warfarin','acetaminophen'])
        self.assertFalse(result['alerts'])
        self.assertTrue(result['uncertain'])
        self.assertIn('Not a complete interaction assessment',result['coverage'])

    def test_missing_database_returns_unavailable_instead_of_clear(self):
        with patch('ddinter_lookup.DB_PATH',self.path.parent/'absent.sqlite3'):
            result=check_pairs(['warfarin','ibuprofen'])
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['alerts'],[])

    def test_full_audit_reports_pass_only_when_checks_really_succeed(self):
        with (patch('audit_critical_interactions.ddinter_lookup.DB_PATH',self.path),
              patch('audit_critical_interactions.rxnorm_ready',return_value=True)):
            report=auditmod.audit(checker=self.check)
        self.assertEqual(report['status'],'pass')
        self.assertEqual(report['passed'],len(auditmod.CRITICAL_CASES)+len(auditmod.PRODUCT_CASES))
        self.assertEqual(report['investigate'],0)

    def test_reference_case_audit_fails_when_checker_misses_alert(self):
        def broken(_names):return dict(status='ready',alerts=[],unrecognized=[],uncertain=[])
        rows=auditmod.check_reference_cases(checker=broken)
        self.assertEqual(sum(r['outcome']=='investigate' for r in rows),len(rows))

if __name__=='__main__':unittest.main()
