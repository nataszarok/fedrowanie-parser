from __future__ import annotations
import re

def norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

NAME_HEADER_RE=re.compile(r'(?i)^(?:nazwisko\s+i\s+imi[ęe]|nazwisko\s+imi[ęe]|imi[ęe]\s+i\s+nazwisko|imi[ęe]\s+nazwisko|nazwisko(?:\s+lekarza)?|dane\s+lekarza)$')
MONEY_RE=re.compile(r'-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})|-?\d{4,9}(?:[,.]\d{2})')
BAD_RE=re.compile(r'(?i)\b(?:lekarz|specjalista|specjalizacja|asystent|rezydent|ordynator|koordynator|kierownik|zast[ęe]pca|oddzia[łl]|klinika|poradnia|pracownia|zak[łl]ad|o[śs]rodek|chirurg|ginekolog|pediatr|psychiatr|radiolog|kardiolog|neurolog|nefrolog|urolog|onkolog|anestez|medycyn|umowa|kontrakt|etat|wynagrodzenie|kwota|brutto|netto)\b')
TOKEN_RE=re.compile(r"^[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźżÀ-ÖØ-öø-ÿ'’-]+$")

def split_row(line):
    s=str(line or '').strip()
    if '|' not in s: return []
    return [norm(x) for x in s.strip('|').split('|')]

def money_value(cell):
    m=MONEY_RE.search(str(cell or ''))
    if not m: return None
    t=m.group(0).replace(' ','')
    if ',' in t: t=t.replace('.','').replace(',','.')
    try: return round(float(t),2)
    except ValueError: return None

def looks_like_person_name(s):
    s=norm(s)
    if not s or len(s)>100 or BAD_RE.search(s) or any(ch.isdigit() for ch in s): return False
    toks=s.split()
    if not (2 <= len(toks) <= 5): return False
    if not all(TOKEN_RE.fullmatch(t) for t in toks): return False
    caps=sum(1 for t in toks if t[:1].isupper())
    upper=sum(1 for t in toks if t.upper()==t and any(c.isalpha() for c in t))
    return upper==len(toks) or caps==len(toks)

def document_person_name_maps(doc):
    raw_map={}; idx_amount_map={}; name_idx=None
    for line in str(doc or '').splitlines():
        cells=split_row(line)
        if not cells: continue
        if all((not c) or re.fullmatch(r':?-{3,}:?',c) for c in cells): continue
        found=[i for i,c in enumerate(cells) if NAME_HEADER_RE.fullmatch(norm(c))]
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
