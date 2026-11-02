


from __future__ import annotations

import argparse
import json
import random
import sqlite3
from contextlib import closing
from pathlib import Path

import ddinter_lookup
import rxnorm_catalog


PUBLIC_PROBES = (
    ('Viagra', 'nitroglycerin', 'documented'),
    ('warfarin', 'ibuprofen', 'documented'),
    ('simvastatin', 'clarithromycin', 'documented'),
    ('Anarex', 'Panadol', 'duplicate'),
    ('Percocet Pill', 'Adderall', 'components'),
    ('Percocet Pill', 'Valium', 'documented'),
    ('grapefruit juice', 'simvastatin', 'documented'),
    ('Adderall', 'nitroglycerin', 'recognized'),
)
PERCOCET_ADDERALL_COMPONENTS = frozenset((
    'acetaminophen', 'oxycodone', 'amphetamine', 'dextroamphetamine'))
SEVERITY_LEVELS = ('Major', 'Moderate', 'Minor', 'Unknown')
SAMPLE_SEED = 7102


def ddinter_statistics(db_path: Path) -> dict:

    if not db_path.is_file():
        return {'ready': False, 'reason': 'ddinter_database_missing'}
    try:
        with closing(sqlite3.connect(f'{db_path.resolve().as_uri()}?mode=ro', uri=True)) as conn:
            counts = {
                'drugs': conn.execute('SELECT COUNT(*) FROM drugs').fetchone()[0],
                'pairs': conn.execute('SELECT COUNT(*) FROM pairs').fetchone()[0],
                'severity_counts': dict(conn.execute(
                    "SELECT COALESCE(level, 'unspecified'), COUNT(*) FROM pairs GROUP BY level")),
            }
            return {'ready': counts['drugs'] > 0 and counts['pairs'] > 0, **counts}
    except sqlite3.Error:
        return {'ready': False, 'reason': 'ddinter_schema_or_read_error'}


def _public_probe(first: str, second: str, expected: str, check_fn) -> dict:
    result = check_fn([first, second])
    if result.get('status') != 'ready':
        return {'medicines': [first, second], 'expected': expected,
                'result': 'investigate', 'reason': 'interaction_lookup_unavailable'}
    alerts = result.get('alerts') or []
    uncertain = result.get('uncertain') or []
    unrecognized = result.get('unrecognized') or []
    ingredients = {str(item.get(field, '')).casefold()
                   for item in (*alerts, *uncertain)
                   for field in ('ingredient_a', 'ingredient_b')}
    if expected == 'documented':
        passed = any(item.get('finding_type') in
                     ('documented_interaction', 'ddinter_severity_only') for item in alerts)
    elif expected == 'duplicate':
        passed = any(item.get('finding_type') == 'duplicate_ingredient' for item in alerts)
    elif expected == 'components':
        passed = not unrecognized and PERCOCET_ADDERALL_COMPONENTS <= ingredients
    else:
        passed = not unrecognized and bool(alerts or uncertain)
    return {
        'medicines': [first, second], 'expected': expected,
        'result': 'pass' if passed else 'investigate',
        'documented_alerts': sum(item.get('finding_type') != 'duplicate_ingredient'
                                 for item in alerts),
        'duplicate_warnings': sum(item.get('finding_type') == 'duplicate_ingredient'
                                  for item in alerts),
        'unassessed_ingredient_comparisons': len(uncertain),
        'unrecognized': unrecognized,
    }


def stratified_samples(db_path: Path, per_level: int = 20) -> dict:


    if not 1 <= per_level <= 32:
        raise ValueError('per_level must be between 1 and 32')
    chosen = {level: [] for level in SEVERITY_LEVELS}
    seen = dict.fromkeys(SEVERITY_LEVELS, 0)
    generator = random.Random(SAMPLE_SEED)
    with closing(sqlite3.connect(f'{db_path.resolve().as_uri()}?mode=ro', uri=True)) as conn:
        cursor = conn.execute('''
            SELECT p.a, p.b, p.level, da.name, db.name
            FROM pairs p JOIN drugs da ON da.id=p.a JOIN drugs db ON db.id=p.b
            WHERE p.level IN ('Major','Moderate','Minor','Unknown')
            ORDER BY p.a, p.b, p.level
        ''')
        for _a, _b, level, first, second in cursor:
            seen[level] += 1
            sample = chosen[level]
            record = (first, second, level)
            if len(sample) < per_level:
                sample.append(record)
            else:
                index = generator.randrange(seen[level])
                if index < per_level:
                    sample[index] = record
    return {level: sorted(chosen[level]) for level in SEVERITY_LEVELS}


def _sample_result(first: str, second: str, level: str, check_fn) -> str:

    if first.casefold() == second.casefold():
        return 'ambiguous_name'
    try:
        result = check_fn([first, second])
    except (sqlite3.Error, ValueError):
        return 'lookup_error'
    if result.get('status') != 'ready':
        return 'lookup_unavailable'
    if result.get('unrecognized'):
        return 'unrecognized_name'
    alerts = result.get('alerts') or []
    gaps = result.get('uncertain') or []
    matched_label = 'DDInter 2.0 · ' + level
    for alert in alerts:
        if (alert.get('finding_type') == 'ddinter_severity_only'
                and alert.get('level') == level):
            return 'record_surfaced'
        if (alert.get('finding_type') == 'documented_interaction'
                and any(ref.get('label') == matched_label
                        for ref in alert.get('evidence_sources', []))):
            return 'label_rule_override'
    if level == 'Unknown' and any(item.get('reason') == 'level_unknown'
                                  and item.get('level') == level for item in gaps):
        return 'unknown_level_review'
    return 'record_not_surfaced'


def extended_audit(db_path: Path, check_fn, per_level: int = 20) -> dict:

    samples = stratified_samples(db_path, per_level)
    categories = {}
    examples = []
    investigated = 0
    checked = 0
    passing = {'record_surfaced', 'label_rule_override', 'unknown_level_review'}
    for level in SEVERITY_LEVELS:
        counts = {}
        for first, second, _ in samples[level]:
            outcome = _sample_result(first, second, level, check_fn)
            counts[outcome] = counts.get(outcome, 0) + 1
            checked += 1
            if outcome not in passing:
                investigated += 1
                if len(examples) < 12:


                    examples.append({'first': first, 'second': second,
                                     'recorded_level': level, 'reason': outcome})
        categories[level] = {'sampled': len(samples[level]), 'outcomes': counts}
    return {
        'sampling': 'fixed-seed reservoir, uniform within each recorded severity level',
        'seed': SAMPLE_SEED, 'requested_per_level': per_level,
        'sampled_total': checked, 'investigate_count': investigated,
        'by_severity': categories, 'investigate_examples': examples,
        'status': 'pass' if investigated == 0 and checked > 0 else 'investigate',
    }


def audit(db_path: Path | None = None, *, check_fn=None, rxnorm_stats_fn=None,
          extended: bool = False, per_level: int = 20) -> dict:

    path = Path(db_path or ddinter_lookup.DB_PATH)
    ddinter = ddinter_statistics(path)
    stats = (rxnorm_stats_fn or rxnorm_catalog.catalog_stats)()
    rxnorm = {key: stats.get(key) for key in (
        'ready', 'release_kind', 'concepts', 'names',
        'products_mapped', 'ingredient_relationships') if key in stats}
    report = {
        'audit': 'MediMate 7.2 local interaction coverage check',
        'ddinter': ddinter, 'rxnorm': rxnorm,
        'cases': [], 'pass_count': 0, 'investigate_count': 0,
        'disclaimer': ('Software identity and interaction-record QA only. '
                       'Not a comprehensive interaction assessment or a safety approval.'),
    }
    if not ddinter['ready'] or not rxnorm.get('ready'):
        report['status'] = 'database_unavailable'
        return report
    check_fn = check_fn or ddinter_lookup.check_pairs
    for first, second, expected in PUBLIC_PROBES:
        try:
            case = _public_probe(first, second, expected, check_fn)
        except (sqlite3.Error, ValueError):
            case = {'medicines': [first, second], 'expected': expected,
                    'result': 'investigate', 'reason': 'lookup_error'}
        report['cases'].append(case)
        if case['result'] == 'pass':
            report['pass_count'] += 1
        else:
            report['investigate_count'] += 1
    report['status'] = 'pass' if report['investigate_count'] == 0 else 'investigate'
    if extended:
        try:
            report['extended'] = extended_audit(path, check_fn, per_level)
            if report['extended']['status'] != 'pass':
                report['status'] = 'investigate'
        except sqlite3.Error:
            report['extended'] = {'status': 'unavailable', 'reason': 'sampling_schema_or_read_error'}
            report['status'] = 'investigate'
    return report


def format_report(report: dict) -> str:
    db, rx = report['ddinter'], report['rxnorm']
    lines = [
        'MediMate local interaction coverage audit (read-only)',
        'DDInter: ' + ('ready' if db['ready'] else db.get('reason', 'unavailable')),
        'RxNorm: ' + ('ready' if rx.get('ready') else 'not ready'),
    ]
    if db['ready']:
        lines.extend((
            f"DDInter drugs: {db['drugs']}; recorded pairs: {db['pairs']}",
            'DDInter severity counts: ' + ', '.join(
                f'{key}={value}' for key, value in sorted(db['severity_counts'].items())),
        ))
    if rx.get('ready'):
        lines.append('RxNorm release: ' + str(rx.get('release_kind', 'unknown')))
        lines.append(f"RxNorm mapped products: {rx.get('products_mapped', 0)}; "
                     f"ingredient links: {rx.get('ingredient_relationships', 0)}")
    for case in report['cases']:
        lines.append(f"{case['result'].upper()}: {case['medicines'][0]} + "
                     f"{case['medicines'][1]} ({case['expected']}; "
                     f"documented={case.get('documented_alerts', 0)}, "
                     f"duplicate={case.get('duplicate_warnings', 0)}, "
                     f"incomplete={case.get('unassessed_ingredient_comparisons', 0)})")
    if 'extended' in report:
        extended = report['extended']
        lines.append('Extended DDInter sample: ' + extended['status'])
        if 'sampled_total' in extended:
            lines.append(f"Recorded pairs sampled: {extended['sampled_total']} "
                         f"({extended['requested_per_level']} per severity requested; "
                         f"fixed seed {extended['seed']})")
            lines.append(f"Extended outcomes: {extended['sampled_total'] - extended['investigate_count']} "
                         f"surfaced or flagged for review; "
                         f"{extended['investigate_count']} need investigation")
            for level, details in extended['by_severity'].items():
                outcomes = ', '.join(f'{key}={value}' for key, value in
                                     sorted(details['outcomes'].items()))
                lines.append(f"  {level}: {details['sampled']} sampled — {outcomes}")
            for example in extended['investigate_examples']:
                lines.append(f"  INVESTIGATE: {example['first']} + {example['second']} "
                             f"({example['recorded_level']}; {example['reason']})")
        elif 'reason' in extended:
            lines.append('Extended audit unavailable: ' + extended['reason'])
    lines.extend((
        f"Fixed probes: {report['pass_count']} passed, "
        f"{report['investigate_count']} need investigation.",
        f"Result: {report['status']}.",
        report['disclaimer'],
        'Contains public drug-index names and aggregate counts only; no personal records.',
    ))
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print the same privacy-safe aggregate report as JSON')
    parser.add_argument('--extended', action='store_true',
                        help='Also check a stratified sample of recorded DDInter pairs')
    parser.add_argument('--per-level', type=int, default=20, metavar='N',
                        help='1–32 recorded pairs per severity (default 20; with --extended)')
    args = parser.parse_args()
    if not 1 <= args.per_level <= 32:
        parser.error('--per-level must be between 1 and 32')
    report = audit(extended=args.extended, per_level=args.per_level)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else format_report(report))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
