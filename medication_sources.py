


from __future__ import annotations

import json
import re
import ssl
import socket
import sqlite3
import time
from collections import OrderedDict
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ddinter_lookup import ALIASES, DB_PATH, normalize, resolve_ingredients
from verified_medicines import SG_PRODUCTS, FOOD_PRODUCTS, FOOD_SOURCE
from rxnorm_catalog import FDA_BRANDS, fuzzy_brands, catalog_search, catalog_resolve

RXNORM_URL = 'https://rxnav.nlm.nih.gov/REST/approximateTerm.json'
RXNORM_DRUGS_URL = 'https://rxnav.nlm.nih.gov/REST/drugs.json'
FDA_URL = 'https://api.fda.gov/drug/label.json'
LABEL_BASE = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='
FIELD_SECTIONS = ('drug_interactions', 'contraindications', 'warnings_and_cautions')
LOCK = Lock()
LABEL_CACHE: OrderedDict[str, tuple[float, dict]] = OrderedDict()

LABEL_TTL = 60 * 60 * 6
MAX_CACHED = 96


def _json_get(url: str, params: dict, timeout: int = 8) -> dict:
    request = Request(url + '?' + urlencode(params), headers={
        'User-Agent': 'MediMateLocal/4.0 (medication reference lookup)',
        'Accept': 'application/json',
    })
    with urlopen(request, timeout=timeout) as resp:

        data = resp.read(1_500_001)
        if len(data) > 1_500_000:
            raise ValueError('too_large')
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError('invalid_response')
    return payload


def suggestions_local(q: str, limit: int = 9) -> dict:
    if not isinstance(q, str) or len(q.strip()) < 2 or len(q) > 70:
        raise ValueError('invalid_query')
    term = normalize(q)


    food_matches = [{'name':name.title(), 'ingredient':'Food or drink · interaction reference',
                     'category':'food', 'source':'US FDA', 'source_url':FOOD_SOURCE}
                    for name in FOOD_PRODUCTS if term in name]
    if not DB_PATH.is_file():
        return {'status':'ready' if food_matches else 'unavailable',
                'matches':food_matches[:limit], 'source':'local', 'external_request':False}
    def entry(name: str, ingredient: str, kind: str) -> dict:
        return {'name': name, 'ingredient': ingredient, 'source': kind}
    matches = list(food_matches)

    for brand, product in SG_PRODUCTS.items():
        if term in brand:
            matches.append({
                'name': product['name'],
                'ingredient': ' + '.join(product['display_ingredients']),
                'source': product['source'], 'source_url': product['source_url'],
                'ingredients': product['ingredients'],
            })

    for brand, product in FDA_BRANDS.items():
        if term in brand:
            matches.append({k:v for k,v in product.items() if k in ('name','ingredient','source','source_url')})


    matches.extend(catalog_search(q,limit=limit))

    for brand, generic in sorted(ALIASES.items()):
        if term in brand and (brand.startswith(term) or len(matches) < 3):
            matches.append(entry(brand.title(), generic.title(), 'local brand alias'))
    with closing(sqlite3.connect(f'{DB_PATH.resolve().as_uri()}?mode=ro', uri=True)) as conn:

        needle = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        rows = conn.execute(
            "SELECT name FROM drugs WHERE norm LIKE ? ESCAPE '\\' "
            "ORDER BY CASE WHEN norm LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END, length(name), name LIMIT 20",
            (needle + '%', needle + '%'),
        ).fetchall()
        if len(matches) < limit:
            rows += conn.execute(
                "SELECT name FROM drugs WHERE norm LIKE ? ESCAPE '\\' "
                "ORDER BY length(name), name LIMIT 15", ('%' + needle + '%',)
            ).fetchall()
    for (name,) in rows:
        matches.append(entry(name, name, 'DDInter vocabulary'))
    if not matches:
        for candidate in fuzzy_brands(q):
            matches.append({'name':candidate['name'], 'ingredient': 'Possible spelling · '+candidate['ingredient'],
                            'source': candidate['source'], 'source_url':candidate['source_url'],
                            'match_type':'spelling_suggestion'})


    def match_rank(item):
        name = normalize(item['name'])
        if name == term:
            exact_source = 0 if item.get('source') == 'NLM RxNorm · mapped components' and item.get('rxcui') else 1
            return (0, exact_source, len(name), name)
        if name.startswith(term + ' ') or name.startswith(term + '[') or name.startswith(term + '/'):
            return (1, len(name), name)
        if name.startswith(term):
            return (2, len(name), name)
        return (3, len(name), name)
    matches.sort(key=match_rank)
    seen = set()
    unique = []
    for item in matches:
        k = (normalize(item['name']), item.get('rxcui') or '')
        if k not in seen:
            seen.add(k)
            unique.append(item)
        if len(unique) == limit:
            break
    return {'status': 'ready', 'matches': unique, 'source': 'local', 'external_request': False}


def _rxnorm_failure(exc: Exception) -> str:


    if isinstance(exc, HTTPError):
        if exc.code == 429:
            return 'remote_rate_limit'
        if exc.code in (401, 403):
            return 'access_denied'
        if exc.code in (500, 502, 503, 504):
            return 'remote_error'
        return 'remote_error'
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout):
        return 'timeout'
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, (ssl.SSLCertVerificationError, ssl.SSLError)) or 'certificate verify failed' in str(reason).lower():
            return 'certificate_error'
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return 'timeout'
        if isinstance(reason, socket.gaierror):
            return 'dns_error'
        return 'network_error'
    if isinstance(exc, (ValueError, TypeError)):
        return 'invalid_response'
    return 'network_error'


def suggestions_rxnorm(q: str) -> dict:
    if not isinstance(q, str) or not (3 <= len(q.strip()) <= 70):
        raise ValueError('invalid_query')

    if not re.fullmatch(r"[\w .+()/-]{3,70}", q.strip(), re.UNICODE):
        raise ValueError('invalid_query')
    term = q.strip()
    try:
        data = _json_get(RXNORM_URL, {'term': term, 'maxEntries': 25, 'option': 1}, timeout=9)
    except (HTTPError, URLError, OSError, ValueError, TypeError, TimeoutError) as exc:
        return {'status': 'unavailable', 'reason': _rxnorm_failure(exc), 'matches': [], 'source': 'RxNorm', 'external_request': True}

    candidates = (data.get('approximateGroup') or {}).get('candidate') or []
    if not isinstance(candidates, list):
        candidates = []
    names = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict) or item.get('source') != 'RXNORM':
            continue
        name = str(item.get('name') or '').strip()
        if not name or len(name) > 190 or normalize(name) in seen:
            continue
        seen.add(normalize(name))
        names.append({'name': name, 'source': 'RxNorm (NLM)', 'rxcui': str(item.get('rxcui', ''))})
        _remember_suggestion(name,str(item.get('rxcui','')))
        if len(names) >= 8:
            break


    if not names:
        try:
            exact = _json_get(RXNORM_DRUGS_URL, {'name': term}, timeout=9)
            groups = (exact.get('drugGroup') or {}).get('conceptGroup') or []
            for group in groups if isinstance(groups, list) else []:
                for entry in group.get('conceptProperties') or []:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get('name') or '').strip()
                    if not name or len(name) > 190 or normalize(name) in seen:
                        continue
                    seen.add(normalize(name))
                    names.append({'name': name, 'source': 'RxNorm (NLM)', 'rxcui': str(entry.get('rxcui', ''))})
                    _remember_suggestion(name,str(entry.get('rxcui','')))
                    if len(names) >= 8:
                        break
                if len(names) >= 8:
                    break
        except (HTTPError, URLError, OSError, ValueError, TypeError, TimeoutError):


            pass
    return {'status': 'ready', 'matches': names, 'source': 'RxNorm (NLM)', 'external_request': True}


RXNORM_ID_URL = 'https://rxnav.nlm.nih.gov/REST/rxcui.json'
RXNORM_RELATED_BASE = 'https://rxnav.nlm.nih.gov/REST/rxcui/'
IDENTITY_CACHE: OrderedDict[tuple[str,str], tuple[float, list[str]]] = OrderedDict()


SUGGESTION_IDS: OrderedDict[tuple[str,str],float] = OrderedDict()
IDENTITY_TTL = 60 * 60 * 12
SUGGESTION_TTL = 60 * 60
INGREDIENT_TTYS = {'IN', 'PIN', 'MIN'}


DRUG_TTYS = {'SCD','SBD','SCDC','SBDC','SCDF','SBDF','GPCK','BPCK','SCDG','SBDG'}


def _remember_suggestion(name: str, rxcui: str) -> None:
    if not name or not re.fullmatch(r'[0-9]{1,12}',rxcui):
        return
    with LOCK:
        SUGGESTION_IDS[(normalize(name),rxcui)]=time.monotonic()
        SUGGESTION_IDS.move_to_end((normalize(name),rxcui))
        while len(SUGGESTION_IDS)>192:
            SUGGESTION_IDS.popitem(last=False)


def _suggested_pair(name: str,rxcui: str) -> bool:
    with LOCK:
        stored=SUGGESTION_IDS.get((normalize(name),rxcui))
        return stored is not None and time.monotonic()-stored<SUGGESTION_TTL


def _related_ingredient_names(rxcui: str) -> list[str]:


    related=_json_get(RXNORM_RELATED_BASE+rxcui+'/related.json',
                      {'tty':'IN PIN'},timeout=8)
    groups=(related.get('relatedGroup') or {}).get('conceptGroup') or []
    by_type={'IN':set(),'PIN':set()}
    for group in groups if isinstance(groups,list) else []:
        if not isinstance(group,dict):continue
        tty=group.get('tty')
        if tty not in by_type:continue
        for concept in group.get('conceptProperties') or []:
            if not isinstance(concept,dict):continue
            value=normalize(concept.get('name'))
            if value and len(value)<=110:by_type[tty].add(value)
    return sorted(by_type['IN'] or by_type['PIN'])


def _history_ingredient_names(rxcui: str) -> list[str]:


    record=_json_get(RXNORM_RELATED_BASE+rxcui+'/historystatus.json',{},timeout=8)
    history=record.get('rxcuiStatusHistory') or {}
    meta=history.get('metaData') or {}
    if meta.get('status')!='Active':return []
    derived=history.get('derivedConcepts') or {}
    listed=derived.get('ingredientConcept') or []
    if isinstance(listed,dict):listed=[listed]
    names={normalize(x.get('ingredientName')) for x in listed if isinstance(x,dict)}
    if not names:
        features=history.get('definitionalFeatures') or {}
        details=features.get('ingredientAndStrength') or []
        if isinstance(details,dict):details=[details]
        names={normalize(x.get('baseName')) for x in details if isinstance(x,dict)}
    return sorted(name for name in names if name and len(name)<=110)


def _rxnorm_ingredient_concepts(rxcui: str, properties: dict | None = None) -> list[str]:
    properties=properties or {}
    tty=str(properties.get('tty') or '')
    if tty=='IN':


        name=normalize(properties.get('name'))
        return [name] if name else []
    if tty=='BN':


        return []
    if tty and tty not in DRUG_TTYS | INGREDIENT_TTYS:
        return []
    related=_related_ingredient_names(rxcui)
    if related:return related


    historical=_history_ingredient_names(rxcui)
    if historical:return historical
    if tty=='PIN':
        name=normalize(properties.get('name'))
        return [name] if name else []
    return []


def _rxnorm_exact_ids(name: str) -> list[str]:
    response=_json_get(RXNORM_ID_URL,{'name':name,'search':0},timeout=8)
    ids=(response.get('idGroup') or {}).get('rxnormId') or []
    return [str(x) for x in ids] if isinstance(ids,list) else []


def rxnorm_ingredients(name: str, rxcui_hint: str | None = None) -> list[str]:


    if not isinstance(name,str) or not re.fullmatch(r'[\w .+()/\[\],-]{2,190}',name.strip(),re.UNICODE):
        return []
    if rxcui_hint is not None and (not isinstance(rxcui_hint,str) or not re.fullmatch(r'[0-9]{1,12}',rxcui_hint)):
        rxcui_hint=None


    offline=catalog_resolve(name,rxcui_hint)
    if offline:return offline
    key=(normalize(name),rxcui_hint or '')
    now=time.monotonic()
    with LOCK:
        cached=IDENTITY_CACHE.get(key)
        if cached and now-cached[0]<IDENTITY_TTL:
            return list(cached[1])
    try:
        ids=[]
        properties_by_id={}
        if rxcui_hint:
            props=_json_get(RXNORM_RELATED_BASE+rxcui_hint+'/properties.json',{},timeout=8).get('properties') or {}
            if isinstance(props,dict) and str(props.get('rxcui'))==rxcui_hint:
                expected={normalize(props.get('name')), normalize(props.get('synonym'))}
                if normalize(name) in expected or _suggested_pair(name,rxcui_hint):
                    ids=[rxcui_hint]
                    properties_by_id[rxcui_hint]=props
        if not ids:
            ids=_rxnorm_exact_ids(name.strip())


        if not 1<=len(ids)<=4 or any(not re.fullmatch(r'[0-9]{1,12}',x) for x in ids):
            return []
        ingredient_sets=[]
        for rxcui in ids:
            props=properties_by_id.get(rxcui)
            if props is None:
                props=_json_get(RXNORM_RELATED_BASE+rxcui+'/properties.json',{},timeout=8).get('properties') or {}
            if not isinstance(props,dict) or not props or (props.get('rxcui') and str(props['rxcui'])!=rxcui):
                return []


            ingredients=_rxnorm_ingredient_concepts(rxcui,props)
            if not ingredients or len(ingredients)>8:return []
            ingredient_sets.append(tuple(ingredients))
        if not ingredient_sets or any(items!=ingredient_sets[0] for items in ingredient_sets):
            return []
        result=list(ingredient_sets[0])
    except (HTTPError,URLError,OSError,ValueError,TimeoutError,TypeError,KeyError):
        return []
    with LOCK:
        IDENTITY_CACHE[key]=(now,result)
        IDENTITY_CACHE.move_to_end(key)
        while len(IDENTITY_CACHE)>128:IDENTITY_CACHE.popitem(last=False)
    return list(result)


def online_mappings_for_unknown(names: list[str], max_names: int = 8,
                                rxnorm_ids: dict | None = None) -> dict[str,list[str]]:

    if not DB_PATH.is_file() or not names:return {}
    with closing(sqlite3.connect(f'{DB_PATH.resolve().as_uri()}?mode=ro',uri=True)) as conn:
        unknown=[n for n in names if not resolve_ingredients(conn,n)]
    selected=list(dict.fromkeys(unknown[:max_names]))
    if not selected:return {}
    hints=rxnorm_ids or {}
    with ThreadPoolExecutor(max_workers=min(3,len(selected))) as pool:
        matches=list(pool.map(lambda name:rxnorm_ingredients(name,hints.get(name)),selected))
    return {name:ingredients for name,ingredients in zip(selected,matches) if ingredients}


SALT = ('sodium', 'hydrochloride', 'hcl', 'calcium', 'potassium', 'maleate', 'tartrate',
        'phosphate', 'acetate', 'citrate', 'succinate', 'mesylate', 'besylate', 'hydrobromide')


def _label_matches_ingredient(meta: dict, ingredient: str) -> bool:


    names = meta.get('generic_name') or []
    if not isinstance(names, list):
        return False
    for drug in names:
        normalized = normalize(drug)
        if normalized == normalize(ingredient):
            return True
        if normalized in {normalize(ingredient) + ' ' + suffix for suffix in SALT}:
            return True
    return False


def _get_fda_label(ingredient: str) -> dict:
    now = time.monotonic()
    with LOCK:
        cached = LABEL_CACHE.get(ingredient)
        if cached and (now - cached[0]) < LABEL_TTL:
            LABEL_CACHE.move_to_end(ingredient)
            return cached[1]
    try:


        data = _json_get(FDA_URL, {
            'search': 'openfda.generic_name:"' + ingredient + '"', 'limit': 15
        }, timeout=9)
        results = data.get('results') or []
        matching = [r for r in results if isinstance(r, dict)
                    and _label_matches_ingredient(r.get('openfda') or {}, ingredient)
                    and any(r.get(s) for s in FIELD_SECTIONS)]
        if not matching:
            result = {'status': 'no_matching_label'}
        else:

            matching.sort(key=lambda r: (bool(r.get('drug_interactions')), str(r.get('effective_time',''))), reverse=True)
            chosen = matching[0]
            metadata = chosen.get('openfda') or {}
            set_id = (str(chosen.get('set_id') or '') or next(iter(metadata.get('spl_set_id') or []), '')).strip()
            source_url = LABEL_BASE + set_id if re.fullmatch(r'[a-fA-F0-9-]{32,40}', set_id) else ''
            parts = {}
            for section in FIELD_SECTIONS:
                value = chosen.get(section) or []
                if isinstance(value, str):value = [value]
                if isinstance(value, list):
                    parts[section] = ' '.join(re.sub(r'\s+', ' ', str(x)) for x in value[:8])[:65000]
            result = {
                'status': 'ready',
                'ingredient': ingredient,
                'label_product': next(iter(metadata.get('generic_name') or [ingredient]), ingredient),
                'label_updated': str(chosen.get('effective_time', '')),
                'source_url': source_url,
                'sections': parts,
            }
    except HTTPError as exc:
        result = {'status': 'no_matching_label' if exc.code == 404 else 'unavailable'}
    except (URLError, OSError, ValueError, TimeoutError, TypeError):
        result = {'status': 'unavailable'}
    with LOCK:
        LABEL_CACHE[ingredient] = (now, result)
        LABEL_CACHE.move_to_end(ingredient)
        while len(LABEL_CACHE) > MAX_CACHED:
            LABEL_CACHE.popitem(last=False)
    return result


def _mentions(text: str, ingredient: str) -> str:

    match = re.search(r'(?<![a-zA-Z0-9])' + re.escape(ingredient) + r'(?![a-zA-Z0-9])', text, flags=re.I)
    if not match:
        return ''
    first = max(0, match.start()-125)
    last = min(len(text), match.end()+165)
    clip = text[first:last].strip()
    return ('…' if first else '') + clip + ('…' if last < len(text) else '')


def crosscheck_fda(names: list[str], online_mappings=None, rxnorm_ids=None) -> dict:


    if not isinstance(names, list) or len(names) < 2 or len(names) > 10:
        raise ValueError('invalid_medicines')
    if any(not isinstance(n, str) or len(n.strip()) < 2 or len(n) > 190 for n in names):
        raise ValueError('invalid_medicines')
    if not DB_PATH.is_file():
        return {'status': 'unavailable', 'mentions': [], 'unknown': names, 'pairs_reviewed': 0}
    with closing(sqlite3.connect(f'{DB_PATH.resolve().as_uri()}?mode=ro', uri=True)) as conn:
        resolved = {n: resolve_ingredients(conn,n,(online_mappings or {}).get(n),(rxnorm_ids or {}).get(n)) for n in names}
    unknown = [n for n in names if not resolved[n]]
    ingredients = {normalize(v['generic']) for product in resolved.values() if product and product.get('kind')!='food'
                   for v in product['ingredients']}
    if len(ingredients) < 2 and not (len(ingredients)==1 and any(p and p.get('kind')=='food' for p in resolved.values())):
        return {'status':'partial','mentions':[],'unknown':unknown,'labels_unavailable':[],
                'labels_not_found':[],'labels_checked':0,'pairs_reviewed':0,
                'source':'FDA drug product labeling via openFDA',
                'limitation':'Text mentions only; absence of a mention does not imply safety.',
                'external_request':False}


    with ThreadPoolExecutor(max_workers=3) as executor:
        by_drug = dict(zip(sorted(ingredients), executor.map(_get_fda_label, sorted(ingredients))))
    seen = set()
    mentions = []
    pair_total = 0
    no_match = set()
    failures = set()
    for i, first in enumerate(names):
        for second in names[i+1:]:
            ra, rb = resolved[first], resolved[second]
            if not ra or not rb:
                continue
            primary_a = {normalize(x['generic']) for x in ra['ingredients']}
            primary_b = {normalize(x['generic']) for x in rb['ingredients']}
            for a in primary_a:
                for b in primary_b:
                    if a == b:
                        continue
                    pair_total += 1
                    for primary, target in [(a, b), (b, a)]:
                        if primary not in by_drug:
                            continue
                        label = by_drug[primary]
                        if label['status'] == 'unavailable':
                            failures.add(primary)
                            continue
                        if label['status'] != 'ready':
                            no_match.add(primary)
                            continue
                        for section in FIELD_SECTIONS:
                            snippet = _mentions(label.get('sections', {}).get(section, ''), target)
                            if not snippet:
                                continue
                            key = (tuple(sorted((a, b))), primary, section)
                            if key in seen:
                                continue
                            seen.add(key)
                            mentions.append({
                                'first': first, 'second': second,
                                'ingredient_a': a, 'ingredient_b': b,
                                'label_for': primary, 'mentions': target,
                                'section': section,
                                'excerpt': snippet, 'source_url': label.get('source_url', ''),
                                'label_product': label.get('label_product', primary),
                                'label_updated': label.get('label_updated', ''),
                                'interpretation': 'label_mention_only',
                            })
    return {
        'status': 'partial' if failures or no_match else 'ready',
        'mentions': mentions[:45],
        'unknown': unknown,
        'labels_unavailable': sorted(failures),
        'labels_not_found': sorted(no_match),
        'labels_checked': len(by_drug),
        'pairs_reviewed': pair_total,
        'source': 'FDA drug product labeling via openFDA',
        'limitation': 'Text mentions only; absence of a mention does not imply safety. US labels may not match local products.',
        'external_request': True,
    }
