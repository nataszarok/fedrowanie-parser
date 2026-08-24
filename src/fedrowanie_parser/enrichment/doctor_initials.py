
from __future__ import annotations
import re

def norm(s):
    """Normalize whitespace and punctuation in a text value."""
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

MONEY=re.compile(r'^\s*-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})\s*(?:z[łl]|PLN)?\s*$',re.I)
INIT_HEADER=re.compile(r'(?i)^(?:inicja[łl]y|identyfikator\s+lekarza)$')
SURNAME_HEADER=re.compile(r'(?i)^nazwisko$')
FIRST_HEADER=re.compile(r'(?i)^imi[ęe]$')

def split_row(s):
    """Split a pipe-delimited source row into normalized cells."""
    return [norm(x) for x in str(s or '').strip().strip('|').split('|')]

def normalize_initials(s):
    """Normalize physician initials to a consistent dotted representation."""
    s=norm(s).replace(' ','')
    if not s: return ''
    # A.B / A.B. / AB -> A.B.
    m=re.fullmatch(r'([A-ZĄĆĘŁŃÓŚŹŻ])\.?([A-ZĄĆĘŁŃÓŚŹŻ])\.?',s,re.I)
    if m:
        return f'{m.group(1).upper()}.{m.group(2).upper()}.'
    return s

def document_initial_maps(doc):
    """
    Structural parser for anonymised physician identifiers:
      INICJAŁY | wynagrodzenie
      Lp | IDENTYFIKATOR LEKARZA | wynagrodzenie
      Lp | Nazwisko | Imię | wynagrodzenie, where source values are abbreviated.
    Returns normalized raw-row -> initials/identifier.
    """
    out={}
    mode=None
    col=None
    surname_col=None
    first_col=None

    for line in str(doc or '').splitlines():
        cells=split_row(line)
        if not cells: continue
        found=[i for i,c in enumerate(cells) if INIT_HEADER.fullmatch(c)]
        if found:
            mode='single'; col=found[0]; surname_col=first_col=None
            continue
        sidx=[i for i,c in enumerate(cells) if SURNAME_HEADER.fullmatch(c)]
        fidx=[i for i,c in enumerate(cells) if FIRST_HEADER.fullmatch(c)]
        if sidx and fidx:
            mode='split'; surname_col=sidx[0]; first_col=fidx[0]; col=None
            continue

        # reset on a clearly new header
        if any(re.search(r'(?i)\b(?:wynagrodzeni\w*|kwota|specjalizacja|oddzia[łl]|klinika)\b',c) for c in cells) \
           and not any(re.fullmatch(r'\d+',c) for c in cells[:2]):
            mode=None; col=surname_col=first_col=None
            continue

        if not any(MONEY.fullmatch(c) for c in cells):
            continue

        val=''
        if mode=='single' and col is not None and col<len(cells):
            c=norm(cells[col])
            if re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ]{2}|[A-ZĄĆĘŁŃÓŚŹŻ]\.?[A-ZĄĆĘŁŃÓŚŹŻ]\.?',c,re.I):
                val=normalize_initials(c)
        elif mode=='split' and surname_col is not None and first_col is not None \
             and surname_col<len(cells) and first_col<len(cells):
            a=norm(cells[surname_col]); b=norm(cells[first_col])
            # Only anonymised/abbreviated source values, never full names.
            if re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]?',a) and re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ]',b):
                val=f'{a}.{b}.'
        if val:
            out[' | '.join(cells)]=val
    return out

def infer_initials_from_row(raw_row):
    """
    Conservative fallback for common anonymised salary-list layouts.
    Avoids scanning arbitrary prose or company names.
    """
    cells=split_row(raw_row)
    if len(cells)<2 or not any(MONEY.fullmatch(c) for c in cells):
        return ''
    nonmoney=[c for c in cells if c and not MONEY.fullmatch(c) and not re.fullmatch(r'\d+',c)]
    # Exact two-letter/dotted identifier as the only textual data cell.
    if len(nonmoney)==1 and re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ]{2}|[A-ZĄĆĘŁŃÓŚŹŻ]\.?[A-ZĄĆĘŁŃÓŚŹŻ]\.?',nonmoney[0],re.I):
        return normalize_initials(nonmoney[0])

    # Split anonymisation: `Lp | A. | P. | amount`, including compound
    # surname initials such as `S-G. | Z.`. Full surnames/names do not match.
    if len(nonmoney)==2:
        a,b=nonmoney
        if re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ](?:-[A-ZĄĆĘŁŃÓŚŹŻ])?\.?|[A-ZĄĆĘŁŃÓŚŹŻ]{2}\.?',a,re.I) \
           and re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ]\.?',b,re.I):
            aa=a.replace('.','').upper()
            bb=b.replace('.','').upper()
            return f'{aa}.{bb}.'
    return ''
