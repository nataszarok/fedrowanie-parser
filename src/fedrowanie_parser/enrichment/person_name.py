"""Extract physician full names from structured response tables."""

from __future__ import annotations

from ..constants import (
    PERSON_NAME_HEADER_RE,
    PERSON_NAME_MONEY_RE,
    PERSON_NAME_BAD_RE,
    PERSON_NAME_TOKEN_RE,
)
import re


__all__ = [
    "norm",
    "split_row",
    "money_value",
    "looks_like_person_name",
    "document_person_name_maps",
    "infer_person_name",
]

def norm(s):
    """Normalize whitespace and punctuation in a text value."""
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

def split_row(line):
    """Split a pipe-delimited source row into normalized cells."""
    s=str(line or '').strip()
    if '|' not in s: return []
    return [norm(x) for x in s.strip('|').split('|')]

def money_value(cell):
    """Parse a monetary value from a single table cell."""
    m=PERSON_NAME_MONEY_RE.search(str(cell or ''))
    if not m: return None
    t=m.group(0).replace(' ','')
    if ',' in t: t=t.replace('.','').replace(',','.')
    try: return round(float(t),2)
    except ValueError: return None

def looks_like_person_name(s):
    """Return whether text plausibly contains a physician's full name."""
    s=norm(s)
    if not s or len(s)>100 or PERSON_NAME_BAD_RE.search(s) or any(ch.isdigit() for ch in s): return False
    toks=s.split()
    if not (2 <= len(toks) <= 5): return False
    if not all(PERSON_NAME_TOKEN_RE.fullmatch(t) for t in toks): return False
    caps=sum(1 for t in toks if t[:1].isupper())
    upper=sum(1 for t in toks if t.upper()==t and any(c.isalpha() for c in t))
    return upper==len(toks) or caps==len(toks)

def document_person_name_maps(doc):
    """Build row-to-person lookup maps from explicit name columns."""
    raw_map={}; idx_amount_map={}; name_idx=None
    for line in str(doc or '').splitlines():
        cells=split_row(line)
        if not cells: continue
        if all((not c) or re.fullmatch(r':?-{3,}:?',c) for c in cells): continue
        found=[i for i,c in enumerate(cells) if PERSON_NAME_HEADER_RE.fullmatch(norm(c))]
        if found:
            name_idx=found[0]; continue
        if name_idx is not None and any(re.search(r'(?i)\b(?:lp\.?|wynagrodzeni\w*|kwota|specjalizacja|oddzia[łl]|klinika|poradnia|forma zatrudn\w*)\b',c) for c in cells) and not any(re.fullmatch(r'\d+',c) for c in cells[:2]):
            name_idx=None; continue
        if name_idx is None or name_idx>=len(cells): continue
        name=norm(cells[name_idx])
        if not looks_like_person_name(name): continue
        raw_map[' | '.join(cells)]=name
        idx=None
        for c in cells[:2]:
            if re.fullmatch(r'\d+',c): idx=int(c); break
        amounts=[money_value(c) for c in cells]; amounts=[x for x in amounts if x is not None]
        if idx is not None and amounts:
            idx_amount_map[(idx,int(round(max(amounts,key=abs)*100)))]=name
    return raw_map,idx_amount_map

def infer_person_name(raw_row, existing_spec='', unit=''):
    """Infer a physician name from a structured row when headers are unavailable."""
    cells=split_row(raw_row)
    if not cells: return ''
    candidates=[]; unit_cf=norm(unit).casefold()
    for c in cells:
        if not c or re.fullmatch(r'\d+',c) or money_value(c) is not None: continue
        if unit_cf and norm(c).casefold()==unit_cf: continue
        if looks_like_person_name(c): candidates.append(norm(c))
    candidates=list(dict.fromkeys(candidates))
    if len(candidates)==1: return candidates[0]
    sp=norm(existing_spec)
    if looks_like_person_name(sp): return sp
    return ''

