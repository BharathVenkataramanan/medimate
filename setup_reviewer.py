from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

from ddinter_lookup import DB_PATH
from rxnorm_catalog import CATALOG_PATH, install_official_catalog, ready as rxnorm_ready

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
ENV = ROOT / '.env'
BUNDLE_NAMES = {'ddinter.sqlite3', 'rxnorm_catalog.sqlite3'}
BUNDLE_VERSION = 1


def _connect(path: Path):
    return sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)


def verify_ddinter(path: Path) -> dict:
    if not path.is_file():
        raise ValueError('DDInter SQLite database not found')
    with closing(_connect(path)) as db:
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('DDInter SQLite integrity check failed')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'drugs', 'pairs'} <= tables:
            raise ValueError('Expected DDInter tables drugs and pairs are missing')
        for table, expected in {'drugs': {'id', 'name', 'norm'}, 'pairs': {'a', 'b', 'level'}}.items():
            actual = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            if not expected <= actual:
                raise ValueError(f'Unexpected DDInter {table} table schema: {sorted(actual)}')
        drugs = db.execute('SELECT COUNT(*) FROM drugs').fetchone()[0]
        pairs = db.execute('SELECT COUNT(*) FROM pairs').fetchone()[0]
        if drugs < 1 or pairs < 1:
            raise ValueError('DDInter index has no drug or interaction rows')
        null_levels = db.execute('SELECT COUNT(*) FROM pairs WHERE level IS NULL').fetchone()[0]
        if null_levels:
            raise ValueError('DDInter interaction rows have missing severity values')
        return {'drugs': drugs, 'pairs': pairs}


def verify_rxnorm(path: Path) -> dict:
    if not rxnorm_ready(path):
        raise ValueError('RxNorm catalogue is absent, incomplete or uses an incompatible schema')
    with closing(_connect(path)) as db:
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('RxNorm catalogue SQLite integrity check failed')
        return {'concepts': db.execute('SELECT COUNT(*) FROM concepts').fetchone()[0],
                'products_mapped': db.execute('SELECT COUNT(DISTINCT product_rxcui) FROM product_ingredients').fetchone()[0]}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def stage_sqlite(source: Path, destination: Path, validate, replace: bool = False):
    source = source.resolve()
    if not source.is_file():
        raise ValueError('Database source file does not exist')
    validate(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        raise ValueError(f'{destination} already exists. Leave it in place or explicitly use --replace.')
    fd, temporary = tempfile.mkstemp(prefix='.medimate-review-', suffix='.sqlite3', dir=destination.parent)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        with closing(_connect(source)) as input_db, closing(sqlite3.connect(temp_path)) as output_db:
            input_db.backup(output_db)
        validate(temp_path)
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)


def status():
    print('MediMate local reviewer setup')
    try:
        d = verify_ddinter(DB_PATH)
        print(f"DDInter: READY ({d['drugs']} drug identities, {d['pairs']} interaction rows)")
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f'DDInter: NOT READY ({exc})')
    try:
        r = verify_rxnorm(CATALOG_PATH)
        print(f"RxNorm: READY ({r['concepts']} concepts, {r['products_mapped']} mapped products)")
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f'RxNorm: NOT READY ({exc})')
    from server import load_env
    load_env()
    print('Medication Q&A:', 'API key configured' if os.environ.get('OPENAI_API_KEY', '').strip() and os.environ['OPENAI_API_KEY'] != 'REPLACE_ON_YOUR_MAC' else 'API key not configured (optional)')
    print('Records: Only the two reference databases are checked here. No browser medicine records are accessed.')
    print('Caution: data presence is not clinical validation; absent interactions do not imply safety.')


def export_bundle(output: Path):
    output = output.resolve()
    inputs = [(DB_PATH, verify_ddinter), (CATALOG_PATH, verify_rxnorm)]
    checks = {}
    for path, validate in inputs:
        checks[path.name] = validate(path)
    manifest = {
        'bundle_version': BUNDLE_VERSION,
        'purpose': 'MediMate local, fictional-data review only',
        'sources': {'ddinter': 'DDInter 2.0 (CC BY-NC-SA 4.0)',
                    'rxnorm': 'NLM RxNorm; verify release-specific redistribution permissions'},
        'files': {name: {'sha256': sha256(path), 'bytes': path.stat().st_size, 'counts': checks[path.name]}
                  for name, (path, _) in zip(('ddinter.sqlite3', 'rxnorm_catalog.sqlite3'), inputs)},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Output already exists; choose a new file name')
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=5,
                             allowZip64=True) as archive:
            for name, (path, _) in zip(('ddinter.sqlite3', 'rxnorm_catalog.sqlite3'), inputs):
                archive.write(path, arcname=name)
            archive.writestr('manifest.json', json.dumps(manifest, indent=2) + '\n')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print('Reference-only bundle created:', output)
    print('Do not commit this archive to GitHub. Share only through an approved, private channel.')
    print('It contains drug reference data, not browser medication histories or an OpenAI API key.')


def import_bundle(path: Path, replace: bool = False):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if set(names) != BUNDLE_NAMES | {'manifest.json'} or len(names) != 3:
            raise ValueError('Unexpected bundle contents. Only the two reference SQLite files and manifest.json are permitted.')
        if any(archive.getinfo(name).file_size > 2_000_000_000 for name in BUNDLE_NAMES):
            raise ValueError('A database entry is unexpectedly large')
        if archive.getinfo('manifest.json').file_size > 20000:
            raise ValueError('Manifest unexpectedly large')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('bundle_version') != BUNDLE_VERSION or set(manifest.get('files', {})) != BUNDLE_NAMES:
            raise ValueError('Bundle manifest version or file list is invalid')
        DATA.mkdir(exist_ok=True)
        if not replace and (DB_PATH.exists() or CATALOG_PATH.exists()):
            raise ValueError('A reference database already exists. Use --replace only after taking a backup.')
        with tempfile.TemporaryDirectory(prefix='.medimate-import-', dir=DATA) as tmp:
            staged = {}
            for name in sorted(BUNDLE_NAMES):
                info = manifest['files'][name]
                if not isinstance(info, dict) or not isinstance(info.get('sha256'), str) or len(info['sha256']) != 64:
                    raise ValueError('Invalid reference bundle manifest')
                output = Path(tmp) / name
                with archive.open(name) as src, output.open('wb') as dest:
                    import shutil
                    shutil.copyfileobj(src, dest, 1024 * 1024)
                if sha256(output) != info['sha256'] or output.stat().st_size != info['bytes']:
                    raise ValueError('Reference bundle checksum mismatch')
                (verify_ddinter if name == 'ddinter.sqlite3' else verify_rxnorm)(output)
                staged[name] = output
            for name, output in staged.items():
                output.replace(DATA / name)
    print('Imported and validated both local reference databases.')
    print('No OpenAI key or private medication records were imported.')


def configure_chat():
    if not sys.stdin.isatty():
        raise ValueError('For safety, API key configuration requires an interactive terminal')
    if ENV.exists():
        raise ValueError('.env already exists; configure it yourself rather than overwriting existing secrets')
    print('Enter an authorised personal or institutional OpenAI API key.')
    print('The key will stay on this computer. It will never be placed in the GitHub ZIP.')
    key = getpass.getpass('OpenAI API key (hidden): ').strip()
    if not key.startswith('sk-') or len(key) < 20 or '\n' in key or '\r' in key:
        raise ValueError('Invalid API key format. No .env created.')
    fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(f'OPENAI_API_KEY={key}\nMEDIMATE_OPENAI_MODEL=gpt-5-mini\nMEDIMATE_PORT=8742\n')
    except Exception:
        ENV.unlink(missing_ok=True)
        raise
    print('Local .env created. Do not upload it or share the API key.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Configure local reference data and optional AI for NUH reviewers')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    sub.add_parser('install-rxnorm')
    d = sub.add_parser('import-ddinter')
    d.add_argument('file', type=Path)
    d.add_argument('--replace', action='store_true')
    e = sub.add_parser('export-bundle')
    e.add_argument('file', type=Path)
    e.add_argument('--confirm-sharing-permission', action='store_true', required=True,
                   help='You confirmed that sharing your reference datasets with NUH is authorised')
    i = sub.add_parser('import-bundle')
    i.add_argument('file', type=Path)
    i.add_argument('--replace', action='store_true')
    sub.add_parser('configure-chat')
    args = parser.parse_args(argv)
    try:
        if args.command == 'status':
            status()
        elif args.command == 'install-rxnorm':
            if CATALOG_PATH.exists():
                print('RxNorm database exists. Run status; do not overwrite a working catalogue.')
                return 1
            print('Downloading and validating the NLM October 2026 publicly available RxNorm subset...')
            result = install_official_catalog()
            print('RxNorm installed:', result['location'])
        elif args.command == 'import-ddinter':
            stage_sqlite(args.file, DB_PATH, verify_ddinter, args.replace)
            print('DDInter installed:', DB_PATH)
        elif args.command == 'export-bundle':
            export_bundle(args.file)
        elif args.command == 'import-bundle':
            import_bundle(args.file, args.replace)
        elif args.command == 'configure-chat':
            configure_chat()
        return 0
    except (OSError, sqlite3.Error, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print('Setup failed:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
