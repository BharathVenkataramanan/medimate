


from __future__ import annotations
import re, sqlite3, unicodedata
from contextlib import closing
from pathlib import Path
from rxnorm_catalog import known_brand, catalog_resolve, ready as catalogue_ready
from verified_medicines import (sg_match, RULE_INDEX, DUPLICATE_ACETAMINOPHEN,
                                FOOD_PRODUCTS, FOOD_SOURCE, RXNORM_CANONICAL)

DB_PATH=Path(__file__).resolve().parent/'data'/'ddinter.sqlite3'
SOURCE='https://ddinter2.scbdd.com/'
TERMS='https://ddinter2.scbdd.com/terms/'

ALIASES={
 'valium':'diazepam','oxycontin':'oxycodone','roxicodone':'oxycodone',
 'nurofen':'ibuprofen','advil':'ibuprofen','brufen':'ibuprofen',
 'aspirin':'acetylsalicylic acid','disprin':'acetylsalicylic acid',
 'panadol':'acetaminophen','tylenol':'acetaminophen','paracetamol':'acetaminophen',
 'coumadin':'warfarin','marevan':'warfarin','eliquis':'apixaban',
 'xarelto':'rivaroxaban','plavix':'clopidogrel','brilinta':'ticagrelor',
 'viagra':'sildenafil','cialis':'tadalafil','gtn':'nitroglycerin',
 'glyceryl trinitrate':'nitroglycerin','nitrostat':'nitroglycerin',
 'zocor':'simvastatin','lipitor':'atorvastatin','crestor':'rosuvastatin',
 'klacid':'clarithromycin','biaxin':'clarithromycin',
 'zoloft':'sertraline','prozac':'fluoxetine','lexapro':'escitalopram',
 'tramal':'tramadol','aldactone':'spironolactone','zestril':'lisinopril',
 'cozaar':'losartan','glucophage':'metformin','amoxil':'amoxicillin',
 'losec':'omeprazole','prilosec':'omeprazole','norvasc':'amlodipine',
 'voltaren':'diclofenac','naprosyn':'naproxen','aleve':'naproxen',
 'bactrim':'sulfamethoxazole / trimethoprim',
}


STRENGTH_SUFFIX=re.compile(r'\s+\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|iu|units?)\s*(?:tablets?|capsules?)?\s*$',re.I)


PRECISE_NITRATE_NAMES=frozenset(('isosorbide mononitrate','isosorbide dinitrate'))
RXNORM_NITRATE_BASE_ALIASES={
    'isosorbide mononitrate':frozenset(('isosorbide','isosorbide mononitrate',
                                       'isosorbide 5-mononitrate','isosorbide-5-mononitrate')),
    'isosorbide dinitrate':frozenset(('isosorbide','isosorbide dinitrate')),
}
RXNORM_NITRATE_FORM=re.compile(
    r'^(?:(?:\d+)\s*hr\s+)?(isosorbide (?:mono|di)nitrate)\s+\d+(?:[.,]\d+)?\s*mg\b',re.I)

def _preserve_verified_nitrate_form(name, verified_components):

    if not isinstance(verified_components,list) or len(verified_components)!=1:
        return verified_components
    entered=normalize(name)
    match=RXNORM_NITRATE_FORM.match(entered)
    precise=entered if entered in PRECISE_NITRATE_NAMES else (match.group(1).casefold() if match else None)
    if precise in PRECISE_NITRATE_NAMES and normalize(verified_components[0]) in RXNORM_NITRATE_BASE_ALIASES[precise]:
        return [precise]
    return verified_components

def normalize(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip().casefold()

def drug_ids(conn, names):


    out={}
    for original in names:
        cleaned=STRENGTH_SUFFIX.sub('',normalize(original))
        generic=ALIASES.get(cleaned,cleaned)
        matches=conn.execute('SELECT id,name FROM drugs WHERE norm=? LIMIT 2',(generic,)).fetchall()
        if not matches and generic=='nitroglycerin':

            pass
        out[original]={'id':matches[0][0],'generic':matches[0][1]} if len(matches)==1 else None
    return out

def _resolved_rxnorm_ingredients(conn, verified):

    mapped=[]
    for component in verified:
        canonical=RXNORM_CANONICAL.get(normalize(component), normalize(component))
        matches=conn.execute('SELECT id,name FROM drugs WHERE norm=? LIMIT 2',(canonical,)).fetchall()
        mapped.append({'id':matches[0][0] if len(matches)==1 else None,
                       'generic':matches[0][1] if len(matches)==1 else canonical})
    return {'ingredients':mapped,'product':None,'kind':'rxnorm',
            'source_url':'https://www.nlm.nih.gov/research/umls/rxnorm/'}

def resolve_ingredients(conn, name, online_names=None, rxcui=None):


    if catalogue_ready() and rxcui is not None:
        verified = catalog_resolve(name, rxcui)
        if verified:
            return _resolved_rxnorm_ingredients(conn, _preserve_verified_nitrate_form(name, verified))
        if online_names is None and not (sg_match(name) or known_brand(name)):


            return None
    if catalogue_ready() and rxcui is None:
        verified = catalog_resolve(name)
        if verified:
            mapped = _resolved_rxnorm_ingredients(conn, _preserve_verified_nitrate_form(name, verified))


            if len(verified) == 1 and mapped['ingredients'][0]['id'] is None:
                exact = drug_ids(conn, [name])[name]
                if exact and normalize(name) == normalize(exact['generic']):
                    return {'ingredients': [exact], 'product': None,
                            'kind': 'ddinter_exact_generic', 'source_url': SOURCE}
            return mapped
    product=sg_match(name)
    if product:
        ids=[]
        for ingredient in product['ingredients']:
            matches=conn.execute('SELECT id,name FROM drugs WHERE norm=? LIMIT 2',(ingredient,)).fetchall()
            if len(matches)!=1:return None
            ids.append({'id':matches[0][0],'generic':matches[0][1]})
        return {'ingredients':ids,'product':product,'source_url':product['source_url']}


    fda_brand=known_brand(name)
    if fda_brand:
        found=[]
        for ingredient in fda_brand['ingredients']:
            rows=conn.execute('SELECT id,name FROM drugs WHERE norm=? LIMIT 2',(ingredient,)).fetchall()
            found.append({'id':rows[0][0] if len(rows)==1 else None,
                          'generic':rows[0][1] if len(rows)==1 else ingredient})
        return {'ingredients':found,'product':fda_brand,'kind':'fda_brand',
                'source_url':fda_brand['source_url']}


    food=FOOD_PRODUCTS.get(normalize(name))
    if food:
        return {'ingredients':[{'id':None,'generic':food}], 'kind':'food',
                'product':None,'source_url':FOOD_SOURCE}
    resolved=drug_ids(conn,[name])[name]
    if resolved:
        return {'ingredients':[resolved],'product':None,'source_url':None}


    if online_names and isinstance(online_names, list) and len(online_names) <= 8:
        mapped=[]
        for ingredient in online_names:
            if not isinstance(ingredient,str) or not ingredient.strip() or len(ingredient)>110:
                return None
            canonical=RXNORM_CANONICAL.get(normalize(ingredient),normalize(ingredient))
            matches=conn.execute('SELECT id,name FROM drugs WHERE norm=? LIMIT 2',
                                 (canonical,)).fetchall()
            if len(matches)==1:
                mapped.append({'id':matches[0][0],'generic':matches[0][1]})
            else:


                mapped.append({'id':None,'generic':canonical})
        if mapped:
            return {'ingredients':mapped,'product':None,'kind':'rxnorm',
                    'source_url':'https://www.nlm.nih.gov/research/umls/rxnorm/'}
    return None


def safety_categories(alerts, uncertain, unrecognized):


    review_pairs={(item['first'],item['second']) for item in uncertain}
    def count_medicine_pairs(rows):
        unique=set()
        for i,item in enumerate(rows):
            first,second=item.get('first'),item.get('second')


            if isinstance(first,str) and isinstance(second,str) and first and second:
                unique.add(('pair',*sorted((first.casefold().strip(),second.casefold().strip()))))
            else:
                unique.add(('unnamed',i))
        return len(unique)
    documented=count_medicine_pairs([item for item in alerts
                                      if item.get('finding_type')!='duplicate_ingredient'])
    duplicates=count_medicine_pairs([item for item in alerts
                                    if item.get('finding_type')=='duplicate_ingredient'])
    return {
        'documented_interactions':documented,
        'duplicate_ingredients':duplicates,
        'needs_review':len(review_pairs),
        'unrecognized_medicines':len(unrecognized),
        'no_documented_interactions':not (alerts or uncertain or unrecognized),
    }


def check_pairs(names, online_mappings=None, rxnorm_ids=None):


    if not DB_PATH.is_file():
        return {'status':'unavailable','errors':['interaction index missing'],'alerts':[],
                'uncertain':[],'unrecognized':[],'pairs_checked':0,
                'safety_categories':None}
    if not isinstance(names,list) or len(names)>60 or any(not isinstance(n,str) or not n.strip() or len(n)>190 for n in names):
        raise ValueError('invalid_names')


    with closing(sqlite3.connect(f'{DB_PATH.resolve().as_uri()}?mode=ro',uri=True)) as conn:
        resolved={n:resolve_ingredients(conn,n,(online_mappings or {}).get(n),(rxnorm_ids or {}).get(n)) for n in names}
        alerts=[];uncertain=[];evidence_pairs=0
        for i,na in enumerate(names):
            for nb in names[i+1:]:
                ra,rb=resolved[na],resolved[nb]
                if not ra or not rb:
                    continue
                ia=ra['ingredients'];ib=rb['ingredients']
                found=set()
                common={x['generic'].casefold() for x in ia}&{x['generic'].casefold() for x in ib}
                if common:
                    for ingredient in sorted(common):
                        rule=DUPLICATE_ACETAMINOPHEN if ingredient=='acetaminophen' else None
                        alerts.append({'first':na,'second':nb,'ingredient_a':ingredient,
                            'ingredient_b':ingredient,'level':rule['level'] if rule else 'Review duplicate ingredient',
                            'effects':rule['effects'] if rule else
                                'Both entries contain the same active ingredient. Unintended duplicate dosing may increase the chance of side effects or overdose.',
                            'advice':rule['advice'] if rule else 'Check whether these are duplicate entries or two products with the same ingredient. Confirm with a pharmacist.',
                            'source':'Ingredient identity: '+(ra['product'] or rb['product'] or {}).get('source','DDInter matched ingredient'),
                            'source_url':rule['source_url'] if rule else (ra['source_url'] or rb['source_url'] or SOURCE),
                            'evidence_sources':[dict(label=(ra['product'] or rb['product'] or {}).get('source','DDInter ingredient identity'),url=ra['source_url'] or rb['source_url'] or SOURCE),
                                                *([dict(label=rule['source'],url=rule['source_url'])] if rule else [])],
                            'finding_type':'duplicate_ingredient',
                            'rule_code':'duplicate_acetaminophen' if rule else 'duplicate_generic'})
                        found.add((ingredient,ingredient))
                for a in ia:
                    for b in ib:
                        if a['id'] is not None and b['id'] is not None and a['id']==b['id']:continue
                        key=frozenset((a['generic'].casefold(),b['generic'].casefold()))
                        if key in found:continue
                        found.add(key)


                        if a['id'] is not None and b['id'] is not None:
                            ordered=sorted((a['id'],b['id']))
                            db_row=conn.execute('SELECT level FROM pairs WHERE a=? AND b=?',ordered).fetchone()
                        else:
                            db_row=None
                        rule=RULE_INDEX.get(key)
                        if rule:
                            alerts.append({'first':na,'second':nb,'ingredient_a':a['generic'],
                                'ingredient_b':b['generic'],'level':rule['level'],
                                'effects':rule['effects'],'advice':rule['advice'],
                                'source':rule['source'],'source_url':rule['source_url'],
                                'evidence_sources':[dict(label=rule['source'],url=rule['source_url'])] +
                                  ([dict(label='DDInter 2.0 · '+db_row[0],url=SOURCE)] if db_row else []),
                                'finding_type':'documented_interaction',
                                'rule_code':rule.get('code') or 'pair_'+ '_'.join(sorted(key)).replace(' ','_')})
                            evidence_pairs+=1
                        elif db_row:
                            row={'first':na,'second':nb,'ingredient_a':a['generic'],
                                'ingredient_b':b['generic'],'level':db_row[0],
                                'effects':'This interaction is recorded by DDInter, but the local DDInter dataset does not specify the side effects or mechanism for this pair. Do not infer that a particular symptom will occur.',
                                'advice':'Ask a pharmacist or prescriber to check the exact medicines, doses, and clinical implications.',
                                'source':'DDInter 2.0','source_url':SOURCE,
                                'evidence_sources':[dict(label='DDInter 2.0 · '+db_row[0],url=SOURCE)],
                                'finding_type':'ddinter_severity_only','rule_code':'ddinter_unspecified'}
                            if db_row[0] in ('Major','Moderate','Minor'):
                                alerts.append(row);evidence_pairs+=1
                            else:
                                uncertain.append(dict(row,reason='level_unknown'))
                        else:
                            uncertain.append({'first':na,'second':nb,'ingredient_a':a['generic'],
                                'ingredient_b':b['generic'],'reason':'no_documented_pair','source':SOURCE})
        unrecognized=[n for n in names if not resolved[n]]
        return {'status':'ready','alerts':alerts,'uncertain':uncertain,
            'unrecognized':unrecognized,
            'safety_categories':safety_categories(alerts,uncertain,unrecognized),
            'pairs_checked':len(names)*(len(names)-1)//2,
            'ingredient_pairs_documented':evidence_pairs,
            'coverage':'Not a complete interaction assessment; no record does not imply safety.',
            'sources':['DDInter 2.0','US FDA prescribing information','Singapore National Drug Formulary','US FDA food interaction information','RxNorm identity'],
            'source':'DDInter 2.0 + source-linked label rules',
            'license':'DDInter CC BY-NC-SA 4.0','source_url':SOURCE}
