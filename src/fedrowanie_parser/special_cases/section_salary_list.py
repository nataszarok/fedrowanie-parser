
from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class SectionSalaryItem:
    index: int
    role: str
    amount: float
    unit: str
    raw_row: str

UNIT_PREFIX_RE=re.compile(
    r'(?i)^(?:oddzia[łl]|pododdzia[łl]|klinika|pracownia|poradni\w*|'
    r'SOR\b|izba przyj[ęe][ćc]|zak[łl]ad|o[śs]rodek)\b'
)

ITEM_START_RE=re.compile(
    r'(?i)^\s*(?P<idx>\d+|[lI])\.\s*(?P<role>lekarz[^—\-|]*?|'
    r'lek\.?[^—\-|]*?|specjalista[^—\-|]*?|asystent[^—\-|]*?|rezydent[^—\-|]*?)\s*'
    r'(?:—|-)\s*(?P<amount>.+?)\s*$'
)

def _norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

def _looks_like_amount_tail(s):
    return bool(re.search(r'\d[\d\s\[\]]*[,.]\d{2}|\d[\d\s\[\]]{2,}\s*z[łl]?\b',s,re.I))

def _parse_amount(s):
    x=str(s or '')
    # Common OCR: brackets represent "1" inside numeric groups.
    x=re.sub(r'(?<=\d)\s*[\[\]]\s*(?=\d)', '1', x)
    x=re.sub(r'(?<=\s)[\[\]]\s*(?=\d)', '1', x)
    # Keep the last monetary-looking token.
    ms=list(re.finditer(r'(\d[\d\s]*[,.]\d{2}|\d[\d\s]{2,})\s*(?:z[łl]|PLN)?',x,re.I))
    if not ms:
        return None
    t=ms[-1].group(1)
    # If decimal mark is a dot, treat last dot as decimal separator.
    if ',' in t:
        a,b=t.rsplit(',',1)
    elif '.' in t:
        a,b=t.rsplit('.',1)
    else:
        a,b=t,'00'
    a=re.sub(r'\D','',a)
    b=re.sub(r'\D','',b)
    if not a:
        return None
    if len(b)==0: b='00'
    if len(b)==1: b=b+'0'
    if len(b)>2: b=b[:2]
    try:
        return round(float(a+'.'+b),2)
    except ValueError:
        return None

def _is_heading_line(s):
    s=_norm(s)
    if not s or len(s)>220:
        return False
    if UNIT_PREFIX_RE.search(s):
        return True
    # Inside an already activated sectioned salary list, tolerate a short
    # standalone OCR heading (e.g. "N$oZ") if it has no amount/doctor item.
    if len(s)<=60 and not re.search(r'(?i)\blekarz\b',s) and not re.search(r'\d[\d\s]*[,.]\d{2}',s):
        return True
    return False

def parse_section_salary_list(doc):
    """
    Parse documents of the shape:
      Oddział X:
      1. lekarz ... — 123 456,78 zł
      2. lekarz ... — ...
      Oddział Y:
      ...

    Supports page breaks, OCR-bracket digits and "l." read instead of "1.".
    Conservative activation requires multiple sections and many salary items.
    """
    lines=str(doc or '').splitlines()
    current=''
    provisional=[]
    heading_positions=[]
    seen_items=0

    for i,line in enumerate(lines):
        s=_norm(line)
        if not s:
            continue
        # Ignore synthetic page markers.
        if re.search(r'(?i)(?:początek|koniec) strony',s):
            continue

        m=ITEM_START_RE.match(s)
        if m and _looks_like_amount_tail(m.group('amount')):
            amount=_parse_amount(m.group('amount'))
            if amount is not None and current:
                idx_raw=m.group('idx')
                idx=1 if idx_raw.lower()=='l' or idx_raw=='I' else int(idx_raw)
                provisional.append(SectionSalaryItem(
                    index=idx,
                    role=_norm(m.group('role')),
                    amount=amount,
                    unit=current,
                    raw_row=s,
                ))
                seen_items+=1
            continue

        # Explicit headings with colon or recognized organizational prefix.
        s_no_pipe=s.rstrip('|').strip()
        explicit_colon=str(line).strip().rstrip('|').strip().endswith(':')
        if UNIT_PREFIX_RE.search(s_no_pipe):
            current=s_no_pipe.rstrip(':').strip()
            heading_positions.append((i,current))
            continue

        # Plain headings such as "Pracownia TK i RTG" are covered above.
        # Unknown OCR heading is accepted only once the list is already active
        # and the following nonempty line is a numbered doctor item.
        if current and _is_heading_line(s_no_pipe):
            nxt=''
            for j in range(i+1,min(i+5,len(lines))):
                z=_norm(lines[j])
                if z and not re.search(r'(?i)(?:początek|koniec) strony',z):
                    nxt=z; break
            if ITEM_START_RE.match(nxt):
                current=s_no_pipe.rstrip(':').strip()
                heading_positions.append((i,current))

    units={x.unit for x in provisional}
    # Generic activation guard.
    if len(provisional)<15 or len(units)<3:
        return []
    return provisional
