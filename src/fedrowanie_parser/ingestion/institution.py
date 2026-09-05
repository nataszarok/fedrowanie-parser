from __future__ import annotations
import re, sqlite3, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

_TRAIL_RE=re.compile(r"(?i)\b(?:wykaz|zestawienie|wynagrodzenia?|lekarze|tabela|informacja|wniosek|pismo|kopia|decyzja)\b.*$")

def normalize_name(s: str) -> str:
    s=unicodedata.normalize('NFKD',str(s or ''))
    s=''.join(c for c in s if not unicodedata.combining(c)).casefold()
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def institution_from_filename(path: Path) -> str:
    stem=path.stem.replace('_',' ').replace('0D0A',' ')
    stem=_TRAIL_RE.sub('',stem).strip(' -_')
    return re.sub(r'\s+',' ',stem).strip()

def resolve_institution(con: sqlite3.Connection | None, detected: str) -> tuple[int|None,str]:
    if con is None: return None,detected
    try:
        rows=con.execute('SELECT pk,name FROM institutions').fetchall()
    except sqlite3.Error:
        return None,detected
    n=normalize_name(detected)
    best=None
    for pk,name in rows:
        nn=normalize_name(name)
        score=SequenceMatcher(None,n,nn).ratio()
        if n and (n in nn or nn in n): score=max(score,.90)
        if best is None or score>best[0]: best=(score,pk,name)
    if best and best[0]>=.84: return best[1],best[2]
    return None,detected
