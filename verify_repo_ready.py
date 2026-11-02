"""Verify that the local review repository includes both substantial reference indexes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MIN_BYTES = {'ddinter.sqlite3': 5 * 1024 * 1024,
             'rxnorm_catalog.sqlite3': 10 * 1024 * 1024}


def main():
    for name, minimum in MIN_BYTES.items():
        path = ROOT / 'data' / name
        if not path.is_file():
            print(f'FAIL: Missing {path.relative_to(ROOT)}')
            return 1
        if path.stat().st_size < minimum:
            print(f'FAIL: {name} is too small to be the full reviewer index ({path.stat().st_size} bytes)')
            return 1
    from setup_reviewer import verify_ddinter, verify_rxnorm
    try:
        dd = verify_ddinter(ROOT / 'data' / 'ddinter.sqlite3')
        rx = verify_rxnorm(ROOT / 'data' / 'rxnorm_catalog.sqlite3')
    except Exception as exc:
        print(f'FAIL: Reference database validation failed: {exc}')
        return 1
    if dd['pairs'] < 1000 or rx['concepts'] < 1000:
        print('FAIL: One or more reference databases contain only a limited number of records')
        return 1
    print(f"PASS: DDInter {dd['pairs']:,} interaction rows, RxNorm {rx['concepts']:,} concepts")
    print('This verifies reference availability and integrity, NOT clinical accuracy or suitability for patient care.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
