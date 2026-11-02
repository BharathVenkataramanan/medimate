


from __future__ import annotations
import argparse
from pathlib import Path
from rxnorm_catalog import (SOURCE_PAGE, import_release,
                            install_official_catalog, verify_official_archive, catalog_stats)

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from-file',type=Path,help='NLM RxNorm RRF ZIP previously downloaded on this computer')
    parser.add_argument('--licensed-full',action='store_true',help='Explicitly import a UMLS-licensed full RxNorm release')
    parser.add_argument('--status',action='store_true')
    args=parser.parse_args()
    if args.status:
        s=catalog_stats()
        if not s['ready']:
            print('RxNorm product-to-ingredient database: not ready (or outdated schema)')
            print('Official NLM download information:',SOURCE_PAGE)
            return 1
        for key in ('release_kind','concepts','names','products_mapped','ingredient_relationships'):
            print(f'{key}: {s.get(key)}')
        print('Product identity mappings are not interaction-safety approvals.')
        return 0
    if args.licensed_full and not args.from_file:
        parser.error('--licensed-full requires --from-file and your own UMLS license')
    try:
        if args.from_file:
            if not args.licensed_full and not verify_official_archive(args.from_file):
                raise ValueError('Unverified public-subset ZIP. Use the pinned October 2026 NLM ZIP; full releases require --licensed-full and a UMLS license.')
            result=import_release(args.from_file,licensed_full=args.licensed_full)
        else:
            print('Downloading checksum-verified RxNorm Current Prescribable Content...',flush=True)
            result=install_official_catalog()
        print('RxNorm product-component database built:')
        print('  Concepts:',result['concepts'])
        print('  Searchable names:',result['names'])
        print('  Completely mapped products:',result['products_mapped'])
        print('  Product-ingredient relationships:',result['ingredient_relationships'])
        print('  Database:',result['location'])
        print('Every product not mapped remains explicitly unresolved; no product is presumed safe.')
        return 0
    except Exception as ex:
        print('RxNorm database build failed:',type(ex).__name__,str(ex))
        print('No existing database or medication records were replaced on failure.')
        return 1

if __name__=='__main__':raise SystemExit(main())
