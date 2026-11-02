


from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import os
import re
import sqlite3
import tempfile
import zipfile

SCHEMA_VERSION = '7.0-ingredient-graph'
TTYS = {'IN', 'PIN', 'MIN', 'BN', 'SCD', 'SBD', 'SCDC', 'SBDC', 'SCDF', 'SBDF', 'GPCK', 'BPCK',
        'SCDG', 'SBDG', 'SCDFP', 'SBDFP'}
PRODUCTS = TTYS - {'IN', 'PIN', 'MIN', 'BN'}

ROUTES = {
    'SCD': {'consists_of': {'SCDC'}, 'has_ingredients': {'MIN'}, 'has_ingredient': {'IN'}},
    'SBD': {'tradename_of': {'SCD'}, 'consists_of': {'SCDC', 'SBDC'}, 'has_ingredient': {'IN'}},
    'SCDC': {'has_ingredient': {'IN'}, 'has_precise_ingredient': {'PIN'}},
    'SBDC': {'tradename_of': {'SCDC'}},
    'SCDF': {'has_ingredient': {'IN'}, 'has_ingredients': {'MIN'}},
    'SBDF': {'tradename_of': {'SCDF'}},
    'SCDFP': {'has_boss': {'IN','PIN'}, 'form_of': {'SCDF'}},
    'SBDFP': {'tradename_of': {'SCDFP'}, 'has_boss': {'IN','PIN'}},
    'SCDG': {'has_ingredient': {'IN'}, 'has_ingredients': {'MIN'}},
    'SBDG': {'tradename_of': {'SCDG'}},
    'MIN': {'has_ingredient': {'IN'}, 'consists_of': {'IN'}},
    'PIN': {'form_of': {'IN'}},
    'GPCK': {'contains': {'SCD', 'SBD'}},
    'BPCK': {'contains': {'SCD', 'SBD'}},
}


def norm(text):
    return ' '.join(str(text or '').casefold().split())


def read_rrf(zf, suffix):
    matches=[info for info in zf.infolist() if info.filename.upper().endswith(suffix)]
    if len(matches)!=1 or matches[0].file_size>650_000_000:
        raise ValueError('Missing, ambiguous or too large: '+suffix)
    return zf.open(matches[0], 'r')


def expand(id, concepts, graph, cache, visiting=frozenset(), depth=0):
    if id in cache:return cache[id]
    if depth>8 or id in visiting or id not in concepts:return None
    tty,name=concepts[id]
    if tty=='IN':return (id,)
    if tty=='PIN':
        bases={v for relation,v in graph.get(id,()) if relation=='form_of' and concepts.get(v,('',''))[0]=='IN'}
        return tuple(sorted(bases)) if len(bases)==1 else (id,)
    if tty=='BN':return None
    links=defaultdict(set)
    for relation,other in graph.get(id,()):
        if concepts.get(other,('',''))[0] in ROUTES.get(tty,{}).get(relation,()):
            links[relation].add(other)
    if tty in ('SBD','SBDC','SBDF','SBDFP','SBDG') and links['tradename_of']:


        children=links['tradename_of']
    elif tty=='SCDC':
        children=links['has_ingredient'] or links['has_precise_ingredient']
    elif tty in ('SCD','SCDF','SCDG'):


        children=links['consists_of'] or links['has_ingredients'] or links['has_ingredient']
    elif tty in ('GPCK','BPCK'):
        children=links['contains']
    else:
        children=set().union(*links.values()) if links else set()
    if not children:return None
    values=set()
    for child in children:
        expanded=expand(child,concepts,graph,cache,visiting|{id},depth+1)
        if not expanded:return None
        values.update(expanded)
    if not values or len(values)>16:return None
    result=tuple(sorted(values))
    cache[id]=result
    return result


def import_graph(archive: Path, output: Path, *, licensed_full: bool=False) -> dict:


    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.rxnorm-graph-',suffix='.sqlite3',dir=output.parent)
    os.close(fd)
    concepts={};graph=defaultdict(list)
    try:
        with zipfile.ZipFile(archive) as zf, sqlite3.connect(tmp) as con:
            con.executescript('''
                CREATE TABLE concepts(rxcui TEXT PRIMARY KEY,name TEXT NOT NULL,tty TEXT NOT NULL);
                CREATE TABLE names(norm TEXT NOT NULL,name TEXT NOT NULL,rxcui TEXT NOT NULL,
                                   PRIMARY KEY(norm,rxcui));
                CREATE INDEX idx_norm ON names(norm);
                CREATE INDEX idx_rxcui ON names(rxcui);
                CREATE TABLE product_ingredients(product_rxcui TEXT NOT NULL,ingredient TEXT NOT NULL,
                    ingredient_rxcui TEXT NOT NULL,PRIMARY KEY(product_rxcui,ingredient_rxcui));
                CREATE INDEX idx_component ON product_ingredients(ingredient_rxcui);
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            with read_rrf(zf,'RXNCONSO.RRF') as inp:
                batch=[]
                for raw in inp:
                    c=raw.decode('utf-8').rstrip('\r\n').split('|')
                    if len(c)<17 or c[1]!='ENG' or c[11]!='RXNORM' or c[12] not in TTYS or c[16]!='N':continue
                    id,tty,name=c[0],c[12],c[14].strip()
                    if not re.fullmatch(r'\d{1,12}',id) or not 1<=len(name)<=190:continue
                    if id not in concepts:concepts[id]=(tty,name)
                    batch.append((norm(name),name,id))
                    if len(batch)>=4000:
                        con.executemany('INSERT OR IGNORE INTO names VALUES (?,?,?)',batch);batch.clear()
                if batch:con.executemany('INSERT OR IGNORE INTO names VALUES (?,?,?)',batch)
            if not concepts:raise ValueError('No active RxNorm concepts in release')
            con.executemany('INSERT INTO concepts VALUES (?,?,?)',
                            ((id,name,tty) for id,(tty,name) in concepts.items()))
            with read_rrf(zf,'RXNREL.RRF') as inp:
                for raw in inp:
                    c=raw.decode('utf-8').rstrip('\r\n').split('|')
                    if len(c)<15 or c[10]!='RXNORM' or c[14] not in ('','N'):continue
                    obj,subject,relation=c[0],c[4],c[7]
                    left=concepts.get(subject,('',''))[0];right=concepts.get(obj,('',''))[0]
                    if right in ROUTES.get(left,{}).get(relation,()):
                        graph[subject].append((relation,obj))

                    if relation in ('ingredient_of','has_ingredient') and left=='IN' and right in PRODUCTS:
                        graph[obj].append(('has_ingredient',subject))
                    elif relation=='ingredient_of' and right=='IN' and left in PRODUCTS:
                        graph[subject].append(('has_ingredient',obj))
            mapped=0;cache={};batch=[]
            for id,(tty,_) in concepts.items():


                if tty not in PRODUCTS and tty!='PIN':continue
                ids=expand(id,concepts,graph,cache)
                if not ids:continue
                mapped+=1
                for component_id in ids:
                    batch.append((id,norm(concepts[component_id][1]),component_id))
                if len(batch)>=5000:
                    con.executemany('INSERT OR IGNORE INTO product_ingredients VALUES (?,?,?)',batch)
                    batch.clear()
            if batch:con.executemany('INSERT OR IGNORE INTO product_ingredients VALUES (?,?,?)',batch)
            if mapped<1:raise ValueError('No source-backed ingredient relationships were resolvable')
            con.executemany('INSERT INTO metadata VALUES (?,?)',[
                ('completed','1'),('schema_version',SCHEMA_VERSION),
                ('source','https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html'),
                ('release_kind','licensed-full' if licensed_full else 'public-prescribable'),
                ('coverage','Verified identities only; interaction safety checked separately')])
            stats={'concepts':len(concepts),'names':con.execute('SELECT COUNT(*) FROM names').fetchone()[0],
                   'products_mapped':mapped,'ingredient_relationships':con.execute('SELECT COUNT(*) FROM product_ingredients').fetchone()[0],
                   'location':str(output)}
            con.commit()
        os.replace(tmp,output)
        return stats
    except Exception:
        if os.path.exists(tmp):os.unlink(tmp)
        raise
