import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import setup_reviewer as setup
from rxnorm_graph import SCHEMA_VERSION


class ReviewerSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        self.dd = self.root / 'sample-ddinter.sqlite3'
        self.rx = self.root / 'sample-rxnorm.sqlite3'
        with closing(sqlite3.connect(self.dd)) as con, con:
            con.executescript('''
                CREATE TABLE drugs (id INTEGER PRIMARY KEY, name TEXT, norm TEXT);
                CREATE TABLE pairs (a INTEGER, b INTEGER, level TEXT);
                INSERT INTO drugs VALUES (1,'Example A','example a'),(2,'Example B','example b');
                INSERT INTO pairs VALUES (1,2,'Major');
            ''')
        with closing(sqlite3.connect(self.rx)) as con, con:
            con.executescript('''
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE concepts (rxcui TEXT PRIMARY KEY,name TEXT,tty TEXT);
                CREATE TABLE product_ingredients (product_rxcui TEXT,ingredient TEXT);
            ''')
            con.executemany('INSERT INTO metadata VALUES (?,?)', [
                ('completed', '1'), ('schema_version', SCHEMA_VERSION)])
            con.execute("INSERT INTO concepts VALUES ('101', 'Example Medicine', 'IN')")
            con.execute("INSERT INTO product_ingredients VALUES ('101','example medicine')")

    def test_ddinter_schema_and_counts(self):
        self.assertEqual(setup.verify_ddinter(self.dd), {'drugs': 2, 'pairs': 1})

    def test_wrong_db_rejected(self):
        with self.assertRaises(ValueError):
            setup.verify_ddinter(self.rx)

    def test_rxnorm_schema_validation(self):
        self.assertEqual(setup.verify_rxnorm(self.rx), {'concepts': 1, 'products_mapped': 1})
        with self.assertRaises(ValueError):
            setup.verify_rxnorm(self.dd)

    def test_safe_ddinter_install_and_no_implicit_overwrite(self):
        target = self.data / 'ddinter.sqlite3'
        setup.stage_sqlite(self.dd, target, setup.verify_ddinter)
        self.assertEqual(setup.verify_ddinter(target)['pairs'], 1)
        with self.assertRaises(ValueError):
            setup.stage_sqlite(self.dd, target, setup.verify_ddinter)

    def test_invalid_import_does_not_overwrite(self):
        target = self.data / 'ddinter.sqlite3'
        setup.stage_sqlite(self.dd, target, setup.verify_ddinter)
        before = setup.sha256(target)
        with self.assertRaises(ValueError):
            setup.stage_sqlite(self.rx, target, setup.verify_ddinter, replace=True)
        self.assertEqual(setup.sha256(target), before)

    def test_bundle_roundtrip_checks_sha256(self):
        output = self.root / 'test-private-reference-bundle.zip'
        with patch.object(setup, 'DB_PATH', self.dd), patch.object(setup, 'CATALOG_PATH', self.rx):
            setup.export_bundle(output)
        with patch.object(setup, 'DB_PATH', self.data / 'ddinter.sqlite3'), \
             patch.object(setup, 'CATALOG_PATH', self.data / 'rxnorm_catalog.sqlite3'), \
             patch.object(setup, 'DATA', self.data):
            setup.import_bundle(output)
            self.assertEqual(setup.verify_ddinter(self.data / 'ddinter.sqlite3')['pairs'], 1)
            self.assertEqual(setup.verify_rxnorm(self.data / 'rxnorm_catalog.sqlite3')['concepts'], 1)
            with self.assertRaises(ValueError):
                setup.import_bundle(output)

    def test_tampered_bundle_is_rejected_before_install(self):
        output = self.root / 'bad.zip'
        with patch.object(setup, 'DB_PATH', self.dd), patch.object(setup, 'CATALOG_PATH', self.rx):
            setup.export_bundle(output)
        changed = self.root / 'tampered.zip'
        with zipfile.ZipFile(output) as orig, zipfile.ZipFile(changed, 'w') as archive:
            for name in orig.namelist():
                archive.writestr(name, orig.read(name) + (b'X' if name == 'ddinter.sqlite3' else b''))
        with patch.object(setup, 'DB_PATH', self.data / 'ddinter.sqlite3'), \
             patch.object(setup, 'CATALOG_PATH', self.data / 'rxnorm_catalog.sqlite3'), \
             patch.object(setup, 'DATA', self.data):
            with self.assertRaises(ValueError):
                setup.import_bundle(changed)
        self.assertFalse((self.data / 'ddinter.sqlite3').exists())
        self.assertFalse((self.data / 'rxnorm_catalog.sqlite3').exists())

    def test_unexpected_bundle_members_rejected(self):
        bad = self.root / 'bad-member.zip'
        with zipfile.ZipFile(bad, 'w') as archive:
            archive.writestr('../.env', 'OPENAI_API_KEY=example')
        with self.assertRaises(ValueError):
            setup.import_bundle(bad)

    def test_configure_chat_requires_interactive_and_does_not_overwrite(self):
        env = self.root / '.env'
        with patch.object(setup, 'ENV', env), patch.object(setup.sys.stdin, 'isatty', return_value=True), \
             patch.object(setup.getpass, 'getpass', return_value='sk-test' + 'x' * 32):
            setup.configure_chat()
            self.assertIn('sk-test', env.read_text())
            with self.assertRaises(ValueError):
                setup.configure_chat()
        self.assertEqual(setup.ENV.name, '.env')

    def test_bad_api_key_never_creates_file(self):
        env = self.root / '.env'
        with patch.object(setup, 'ENV', env), patch.object(setup.sys.stdin, 'isatty', return_value=True), \
             patch.object(setup.getpass, 'getpass', return_value='not-a-key'):
            with self.assertRaises(ValueError):
                setup.configure_chat()
        self.assertFalse(env.exists())


if __name__ == '__main__':
    unittest.main()
