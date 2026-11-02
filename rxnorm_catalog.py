


from __future__ import annotations

import difflib
import hashlib
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.request import Request, urlopen
from rxnorm_graph import import_graph, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / 'data' / 'rxnorm_catalog.sqlite3'


SOURCE_URL = 'https://download.nlm.nih.gov/umls/kss/rxnorm/RxNorm_full_prescribe_10052026.zip'
SOURCE_MD5 = 'a3bfab544c6a67c127ebcd10ab914aa9'
SOURCE_PAGE = 'https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html'
VALID_TTYS = {'IN','PIN','MIN','BN','SCD','SBD','SCDC','SBDC','SCDF','SBDF','GPCK','BPCK','SCDG','SBDG'}
PRODUCT_TTYS = VALID_TTYS - {'IN','PIN','MIN','BN'}
LINK_RELAS = {'has_ingredient','ingredient_of','has_precise_ingredient','precise_ingredient_of'}


FDA_BRANDS = {


    'bactrim': {
        'name': 'Bactrim', 'ingredients': ['sulfamethoxazole', 'trimethoprim'],
        'ingredient': 'Sulfamethoxazole + trimethoprim',
        'source': 'DailyMed · Bactrim label',
        'source_url': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f59d0c04-9c66-4d53-a0e1-cb55570deb62',
    },
    'bactrim ds': {
        'name': 'Bactrim DS', 'ingredients': ['sulfamethoxazole', 'trimethoprim'],
        'ingredient': 'Sulfamethoxazole + trimethoprim',
        'source': 'DailyMed · Bactrim label',
        'source_url': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f59d0c04-9c66-4d53-a0e1-cb55570deb62',
    },
    'co-trimoxazole': {
        'name': 'Co-trimoxazole', 'ingredients': ['sulfamethoxazole', 'trimethoprim'],
        'ingredient': 'Sulfamethoxazole + trimethoprim',
        'source': 'Singapore National Drug Formulary',
        'source_url': 'https://www.ndf.gov.sg/about-drugs/active-ingredient/m00321/',
    },
    'cotrimoxazole': {
        'name': 'Co-trimoxazole', 'ingredients': ['sulfamethoxazole', 'trimethoprim'],
        'ingredient': 'Sulfamethoxazole + trimethoprim',
        'source': 'Singapore National Drug Formulary',
        'source_url': 'https://www.ndf.gov.sg/about-drugs/active-ingredient/m00321/',
    },
    'adderall': {
        'name': 'Adderall', 'ingredients': ['amphetamine','dextroamphetamine'],
        'ingredient': 'Amphetamine + dextroamphetamine (mixed salts)',
        'source': 'DailyMed · FDA drug label',
        'source_url': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f22635fe-821d-4cde-aa12-419f8b53db81',
    },
}


def norm(text: str) -> str:
    return ' '.join(str(text or '').casefold().split())


def known_brand(name: str) -> dict | None:
    return FDA_BRANDS.get(norm(name))


def fuzzy_brands(query: str) -> list[dict]:

    key=norm(query)
    matches=difflib.get_close_matches(key, list(FDA_BRANDS), n=4, cutoff=0.72)
    return [dict(FDA_BRANDS[name], match_type='spelling_suggestion') for name in matches if name!=key]


def ready(db_path: Path | None=None) -> bool:
    p=Path(db_path or CATALOG_PATH)
    if not p.is_file():return False
    try:
        with closing(sqlite3.connect(f'{p.resolve().as_uri()}?mode=ro',uri=True)) as con:
            return (con.execute("SELECT value FROM metadata WHERE key='completed'").fetchone()==('1',) and con.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()==(SCHEMA_VERSION,))
    except sqlite3.Error:return False


def catalog_search(query: str, limit: int=8, db_path: Path | None=None) -> list[dict]:

    p=Path(db_path or CATALOG_PATH)
    if not ready(p):return []
    q=norm(query)
    if len(q)<2 or len(q)>70:return []
    needle=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    with closing(sqlite3.connect(f'{p.resolve().as_uri()}?mode=ro',uri=True)) as con:
        rows=con.execute("""SELECT n.name,n.rxcui,c.tty FROM names n JOIN concepts c ON c.rxcui=n.rxcui
            WHERE n.norm LIKE ? ESCAPE '\\' AND c.tty!='BN'
              AND (c.tty IN ('IN','PIN') OR EXISTS(SELECT 1 FROM product_ingredients pi WHERE pi.product_rxcui=c.rxcui))
            ORDER BY CASE WHEN n.norm=? THEN 0 WHEN n.norm LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END,
                     CASE WHEN c.tty='SBD' THEN 0 WHEN c.tty='SCD' THEN 1 ELSE 2 END,
                     length(n.name),n.name LIMIT ?""",
            ('%'+needle+'%',q,needle+'%',min(80,max(10,limit*10)))).fetchall()
        result=[];seen=set()
        for name,rxcui,tty in rows:
            k=(norm(name),rxcui)
            if k in seen:continue
            seen.add(k)
            items=[r[0] for r in con.execute('SELECT ingredient FROM product_ingredients WHERE product_rxcui=? ORDER BY ingredient',(rxcui,))]
            result.append({'name':name,'rxcui':rxcui,
                'ingredient':' + '.join(items) if items else name,
                'source':'NLM RxNorm · mapped components','identity_status':'resolved'})
            if len(result)>=limit:break
        return result


def catalog_resolve(name: str, rxcui: str | None=None, db_path: Path | None=None) -> list[str]:

    p=Path(db_path or CATALOG_PATH)
    if not ready(p) or not isinstance(name,str) or not 1<=len(name)<=190:return []
    if rxcui is not None and (not isinstance(rxcui,str) or not re.fullmatch('[0-9]{1,12}',rxcui)):
        return []
    with closing(sqlite3.connect(f'{p.resolve().as_uri()}?mode=ro',uri=True)) as con:
        query='SELECT DISTINCT c.rxcui,c.tty,c.name FROM concepts c JOIN names n ON n.rxcui=c.rxcui WHERE n.norm=?'
        args=[norm(name)]
        if rxcui is not None:query+=' AND c.rxcui=?';args.append(rxcui)
        rows=con.execute(query+' LIMIT 10',args).fetchall()
        if not rows or len(rows)>8:return []
        sets=[]
        for identity,tty,canonical in rows:
            if tty=='IN':ingredients=[norm(canonical)]
            elif tty=='PIN':
                bases=[r[0] for r in con.execute('SELECT ingredient FROM product_ingredients WHERE product_rxcui=? ORDER BY ingredient',(identity,))]
                ingredients=bases or [norm(canonical)]
            elif tty=='BN':return []
            elif tty in PRODUCT_TTYS:
                ingredients=[r[0] for r in con.execute('SELECT ingredient FROM product_ingredients WHERE product_rxcui=? ORDER BY ingredient',(identity,))]
            else:return []
            if not ingredients or len(ingredients)>16:return []
            sets.append(tuple(sorted(set(ingredients))))
        return list(sets[0]) if all(v==sets[0] for v in sets) else []


def catalog_stats(db_path: Path | None=None) -> dict:
    p=Path(db_path or CATALOG_PATH)
    if not ready(p):return {'ready':False,'reason':'not_installed_or_outdated'}
    with closing(sqlite3.connect(f'{p.resolve().as_uri()}?mode=ro',uri=True)) as con:
        data=dict(con.execute('SELECT key,value FROM metadata'))
        return {'ready':True, 'source':data.get('source'), 'release_kind':data.get('release_kind'),
                'concepts':con.execute('SELECT COUNT(*) FROM concepts').fetchone()[0],
                'names':con.execute('SELECT COUNT(*) FROM names').fetchone()[0],
                'products_mapped':con.execute('SELECT COUNT(DISTINCT product_rxcui) FROM product_ingredients').fetchone()[0],
                'ingredient_relationships':con.execute('SELECT COUNT(*) FROM product_ingredients').fetchone()[0]}


def verify_official_archive(archive: Path) -> bool:

    digest=hashlib.md5(usedforsecurity=False)
    with Path(archive).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()==SOURCE_MD5


def import_release(archive: Path, output: Path | None=None, *, licensed_full: bool=False) -> dict:
    return import_graph(Path(archive), Path(output or CATALOG_PATH), licensed_full=licensed_full)


def install_official_catalog(url: str=SOURCE_URL, expected_md5: str=SOURCE_MD5,
                             output: Path | None=None) -> dict:

    if url!=SOURCE_URL or expected_md5!=SOURCE_MD5:raise ValueError('unverified_release')
    with tempfile.TemporaryDirectory(prefix='medimate-nlm-') as temp:
        filename=Path(temp)/'rxnorm_prescribe.zip'
        req=Request(url,headers={'User-Agent':'MediMate/6.9 RxNorm catalogue installer'})
        digest=hashlib.md5(usedforsecurity=False)
        total=0
        with urlopen(req,timeout=35) as response, filename.open('wb') as fout:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>150_000_000:raise ValueError('archive_too_large')
                digest.update(chunk);fout.write(chunk)
        if digest.hexdigest()!=expected_md5:raise ValueError('RxNorm archive checksum mismatch')
        return import_release(filename,output)
