


from __future__ import annotations
import argparse
import json
import sys

import ddinter_lookup
from rxnorm_catalog import ready as rxnorm_ready
from verified_medicines import RULE_INDEX


CRITICAL_CASES = (
    ('sildenafil', 'nitroglycerin', 'PDE5 inhibitor / nitrate'),
    ('tadalafil', 'isosorbide mononitrate', 'PDE5 inhibitor / nitrate'),
    ('oxycodone', 'diazepam', 'opioid / benzodiazepine'),
    ('warfarin', 'ibuprofen', 'anticoagulant / NSAID'),
    ('simvastatin', 'clarithromycin', 'statin / macrolide'),
    ('methotrexate', 'trimethoprim', 'antifolate interaction'),
    ('warfarin', 'trimethoprim', 'anticoagulant / antibiotic'),
    ('linezolid', 'sertraline', 'serotonergic interaction'),
    ('linezolid', 'fluoxetine', 'serotonergic interaction'),
    ('linezolid', 'escitalopram', 'serotonergic interaction'),
    ('lithium', 'ibuprofen', 'lithium / NSAID'),
    ('lithium', 'naproxen', 'lithium / NSAID'),
    ('lithium carbonate', 'ibuprofen', 'lithium salt / NSAID'),
    ('lithium cation', 'naproxen', 'RxNorm lithium ingredient / NSAID'),
    ('spironolactone', 'lisinopril', 'hyperkalemia risk'),
    ('spironolactone', 'losartan', 'hyperkalemia risk'),
)


PRODUCT_CASES = (
    ('Bactrim', 'warfarin', 'trimethoprim', 'warfarin', 'Bactrim composition'),
    ('Bactrim DS', 'methotrexate', 'trimethoprim', 'methotrexate', 'Bactrim DS composition'),
    ('Co-trimoxazole', 'methotrexate', 'trimethoprim', 'methotrexate', 'NDF co-trimoxazole synonym'),
    ('Cotrimoxazole', 'warfarin', 'trimethoprim', 'warfarin', 'NDF co-trimoxazole synonym'),
)


def check_reference_cases(checker=None):

    checker = checker or ddinter_lookup.check_pairs
    rows = []
    for left, right, category in CRITICAL_CASES:
        rule = RULE_INDEX.get(frozenset((left, right)))
        if not rule or not str(rule.get('source_url', '')).startswith('https://'):
            rows.append({'first':left, 'second':right,'category':category,
                         'outcome':'investigate', 'reason':'curated_source_rule_missing'})
            continue
        try:
            result = checker([left, right])
            if result.get('status') != 'ready':
                reason = 'database_unavailable'
                match = None
            else:
                match = next((finding for finding in result.get('alerts', [])
                              if finding.get('finding_type') == 'documented_interaction'
                              and frozenset((str(finding.get('ingredient_a', '')).casefold(),
                                             str(finding.get('ingredient_b', '')).casefold()))
                                     == frozenset((left, right))
                              and finding.get('source_url') == rule['source_url']
                              and finding.get('effects') and finding.get('advice')), None)
                reason = ('unrecognized_name' if result.get('unrecognized')
                          else 'reference_warning_not_surfaced')
            rows.append({'first':left, 'second':right,'category':category,
                         'outcome':'pass' if match else 'investigate',
                         'reason':'source_linked_warning_found' if match else reason,
                         'source_url':rule['source_url'],
                         'unrecognized':result.get('unrecognized', []) if result else []})
        except Exception as exc:

            rows.append({'first':left,'second':right,'category':category,
                         'outcome':'investigate','reason':type(exc).__name__})
    for product, other, ingredient, comparator, category in PRODUCT_CASES:
        rule=RULE_INDEX.get(frozenset((ingredient,comparator)))
        try:
            result=checker([product,other])
            match=next((a for a in result.get('alerts',[])
                        if a.get('finding_type')=='documented_interaction'
                        and a.get('source_url')==rule['source_url']
                        and frozenset((str(a.get('ingredient_a','')).casefold(),
                                       str(a.get('ingredient_b','')).casefold()))
                              ==frozenset((ingredient,comparator))),None) if rule else None


            compared={str(a.get(k,'')).casefold() for a in
                      (result.get('alerts',[])+result.get('uncertain',[]))
                      for k in ('ingredient_a','ingredient_b')}
            source_components={'sulfamethoxazole','trimethoprim'}
            valid=bool(match) and not result.get('unrecognized') and source_components <= compared
            rows.append({'first':product,'second':other,'category':category,
                         'outcome':'pass' if valid else 'investigate',
                         'reason':'verified_combination_warning_found' if valid else 'combination_resolution_gap',
                         'source_url':rule['source_url'] if rule else None,
                         'unrecognized':result.get('unrecognized',[])})
        except Exception as exc:
            rows.append({'first':product,'second':other,'category':category,
                         'outcome':'investigate','reason':type(exc).__name__})
    return rows


def audit(*, checker=None, require_real_databases=True):
    ddinter_available=ddinter_lookup.DB_PATH.is_file()
    rxnorm_available=rxnorm_ready()
    if require_real_databases and not ddinter_available:
        return {'status':'database_unavailable', 'message':'DDInter SQLite is absent on this machine; no real-data claims were made.',
                'ddinter_ready':False,'rxnorm_ready':rxnorm_available,
                'count':0,'passed':0,'investigate':0,'cases':[]}
    rows=check_reference_cases(checker)
    failures=sum(item['outcome']!='pass' for item in rows)
    return {'status':'pass' if failures==0 else 'investigate',
            'scope':'Software detection of preselected source-linked cases, not a comprehensive clinical assessment',
            'ddinter_ready':ddinter_available,'rxnorm_ready':rxnorm_available,
            'count':len(rows),'passed':len(rows)-failures,'investigate':failures,'cases':rows,
            'notice':('No alert does not establish safety. Some product aliases, doses, and local drug catalogue '
                      'variants are not tested by these ingredient-name probes.')}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args=parser.parse_args(argv)
    report=audit()
    if args.json:
        print(json.dumps(report,indent=2,ensure_ascii=False))
    else:
        print('MediMate current release: read-only clinical regression audit')
        print('DDInter installed:',report['ddinter_ready'],'| RxNorm installed:',report['rxnorm_ready'])
        if report['status']=='database_unavailable':
            print('CHECKPOINT: DATABASE UNAVAILABLE - no real-data checks performed')
        else:
            for item in report['cases']:
                print(('[PASS]' if item['outcome']=='pass' else '[INVESTIGATE]'),
                      item['first']+' + '+item['second'], '-',item['reason'])
            print('SOURCE-LINKED TESTS:',report['passed'],'/',report['count'],
                  '| investigate:',report['investigate'])
            print('CHECKPOINT:',report['status'].upper())
        print('No medication logs, dose histories, or family profiles were read.')
        print('This tests known examples, NOT the sensitivity of the overall interaction checker.')
    return 0 if report['status']=='pass' else 1


if __name__=='__main__':
    sys.exit(main())
