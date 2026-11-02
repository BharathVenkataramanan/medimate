
import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import audit_interaction_coverage as coverage
from rxnorm_catalog import catalog_resolve, catalog_search, catalog_stats, ready
from rxnorm_graph import SCHEMA_VERSION
from tests import test_interaction_safety as fixture_suite


class CoverageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):

        fixture_suite.InteractionSafety71Tests.setUpClass()
        cls.db = fixture_suite.InteractionSafety71Tests.db

    @classmethod
    def tearDownClass(cls):
        fixture_suite.InteractionSafety71Tests.tearDownClass()

    def run_audit(self, location=None, *, extended=False, per_level=20):
        with (patch('ddinter_lookup.DB_PATH', self.db),
              patch('ddinter_lookup.catalogue_ready', return_value=True),
              patch('ddinter_lookup.catalog_resolve',
                    side_effect=fixture_suite.InteractionSafety71Tests.fake_catalog)):
            return coverage.audit(
                location or self.db, extended=extended, per_level=per_level,
                rxnorm_stats_fn=lambda: {
                    'ready': True, 'release_kind': 'synthetic', 'concepts': 4,
                    'names': 4, 'products_mapped': 1,
                    'ingredient_relationships': 2})

    def test_all_fixed_public_probes_pass_with_synthetic_fixture(self):
        result = self.run_audit()
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['pass_count'], len(coverage.PUBLIC_PROBES))
        self.assertEqual(result['investigate_count'], 0)
        self.assertEqual(result['ddinter']['pairs'], 4)
        self.assertEqual(result['ddinter']['severity_counts']['Major'], 1)
        self.assertEqual(result['ddinter']['severity_counts']['Unknown'], 1)

    def test_audit_does_not_modify_database(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        before_mtime = self.db.stat().st_mtime_ns
        self.run_audit(extended=True, per_level=1)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertEqual(self.db.stat().st_mtime_ns, before_mtime)

    def test_missing_ddinter_database_is_reported_without_creating_it(self):
        missing = self.db.parent / 'does_not_exist.sqlite3'
        report = self.run_audit(missing)
        self.assertEqual(report['status'], 'database_unavailable')
        self.assertEqual(report['cases'], [])
        self.assertFalse(missing.exists())

    def test_missing_record_is_not_misrepresented_as_safety(self):
        failed = coverage._public_probe('Unknown Example', 'Adderall', 'recognized',
            lambda _: {'status': 'ready', 'alerts': [], 'uncertain': [],
                       'unrecognized': ['Unknown Example']})
        self.assertEqual(failed['result'], 'investigate')

    def test_output_contains_only_public_probes_and_aggregate_counts(self):
        text = coverage.format_report(self.run_audit())
        self.assertNotIn(str(self.db), text)
        self.assertIn('No personal records'.lower(), text.lower())
        self.assertIn('Percocet Pill + Adderall', text)

    def test_extended_stratified_sample_matches_all_four_synthetic_levels(self):
        result = self.run_audit(extended=True, per_level=1)
        self.assertEqual(result['status'], 'pass')
        sampled = result['extended']
        self.assertEqual(sampled['sampled_total'], 4)
        self.assertEqual(sampled['investigate_count'], 0)
        for severity in ('Major', 'Moderate', 'Minor'):
            self.assertEqual(sampled['by_severity'][severity]['outcomes'],
                             {'record_surfaced': 1})
        self.assertEqual(sampled['by_severity']['Unknown']['outcomes'],
                         {'unknown_level_review': 1})
        summary = coverage.format_report(result)
        self.assertIn('Extended DDInter sample: pass', summary)
        self.assertIn('Extended outcomes: 4 surfaced or flagged for review; '
                      '0 need investigation', summary)
        self.assertIn('Fixed probes: 8 passed, 0 need investigation.', summary)
        self.assertIn('Result: pass.', summary)

    def test_report_counts_extended_failures_separately_from_fixed_probes(self):
        result = self.run_audit(extended=True, per_level=1)
        result['status'] = 'investigate'
        result['extended']['status'] = 'investigate'
        result['extended']['investigate_count'] = 1
        summary = coverage.format_report(result)
        self.assertIn('Extended outcomes: 3 surfaced or flagged for review; '
                      '1 need investigation', summary)
        self.assertIn('Fixed probes: 8 passed, 0 need investigation.', summary)
        self.assertIn('Result: investigate.', summary)

    def test_extended_sampling_is_deterministic(self):
        first = coverage.stratified_samples(self.db, 1)
        second = coverage.stratified_samples(self.db, 1)
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            coverage.stratified_samples(self.db, 0)
        with self.assertRaises(ValueError):
            coverage.stratified_samples(self.db, 33)

    def test_unknown_level_without_review_is_investigated(self):
        result = coverage._sample_result('fixture-a', 'fixture-e', 'Unknown',
            lambda _: {'status': 'ready', 'alerts': [], 'uncertain': [],
                       'unrecognized': []})
        self.assertEqual(result, 'record_not_surfaced')

    def test_label_backed_rule_can_preserve_a_recorded_unknown_ddinter_row(self):
        result = coverage._sample_result('fixture-a', 'fixture-e', 'Unknown',
            lambda _: {'status': 'ready', 'alerts': [{
                'finding_type': 'documented_interaction',
                'evidence_sources': [{'label': 'DDInter 2.0 · Unknown'}]}],
                'uncertain': [], 'unrecognized': []})
        self.assertEqual(result, 'label_rule_override')

    def test_unrecognized_public_drug_name_is_investigated(self):
        result = coverage._sample_result('fixture-a', 'fixture-e', 'Major',
            lambda _: {'status': 'ready', 'alerts': [], 'uncertain': [],
                       'unrecognized': ['fixture-e']})
        self.assertEqual(result, 'unrecognized_name')


class RxNormReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = Path(self.temp.name) / 'catalog.sqlite3'
        with closing(sqlite3.connect(self.catalog)) as conn, conn:
            conn.executescript('''
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE concepts(rxcui TEXT PRIMARY KEY, name TEXT, tty TEXT);
                CREATE TABLE names(norm TEXT, name TEXT, rxcui TEXT);
                CREATE TABLE product_ingredients(product_rxcui TEXT, ingredient TEXT,
                                                 ingredient_rxcui TEXT);
            ''')
            conn.executemany('INSERT INTO metadata VALUES (?, ?)', [
                ('completed', '1'), ('schema_version', SCHEMA_VERSION),
                ('release_kind', 'synthetic')])
            conn.execute('INSERT INTO concepts VALUES (?, ?, ?)',
                         ('12345', 'Example pill', 'SCD'))
            conn.execute('INSERT INTO names VALUES (?, ?, ?)',
                         ('example pill', 'Example pill', '12345'))
            conn.execute('INSERT INTO product_ingredients VALUES (?, ?, ?)',
                         ('12345', 'acetaminophen', '44'))

    def test_exact_product_identity_is_readable_without_database_leak(self):
        self.assertTrue(ready(self.catalog))
        self.assertEqual(catalog_resolve('Example pill', db_path=self.catalog),
                         ['acetaminophen'])
        self.assertEqual(catalog_search('Example', db_path=self.catalog)[0]['rxcui'],
                         '12345')
        self.assertEqual(catalog_stats(self.catalog)['products_mapped'], 1)

    def test_invalid_selected_identity_fails_closed(self):
        self.assertEqual(catalog_resolve('Example pill', '99999', self.catalog), [])
        self.assertEqual(catalog_resolve('Example pill', 'not-a-number', self.catalog), [])


if __name__ == '__main__':
    unittest.main()
