"""Recover organizational units from explicit table columns and section headings."""


from __future__ import annotations

from ..constants import (
    UNIT_COLUMN_HEADER_RE,
    UNIT_COLUMN_HEADER_LIKE_RE,
    UNIT_COLUMN_MONEY_RE,
    UNIT_COLUMN_SECTION_HEADING_RE,
    UNIT_COLUMN_SALARY_ITEM_RE,
)
import re
from typing import Optional


__all__ = [
    "split_markdown_row",
    "is_separator_row",
    "unit_column_indexes",
    "clean_unit_value",
    "document_unit_row_map",
    "section_unit_map",
    "inline_ocr_section_unit",
    "document_unit_index_amount_map",
    "shifted_row_unit_candidate",
]

def split_markdown_row(line:str)->list[str]:
    """Split a Markdown table row into normalized cells."""
    s=str(line or '').strip()
    if not s.startswith('|'):
        return []
    if s.startswith('|'): s=s[1:]
    if s.endswith('|'): s=s[:-1]
    return [_norm(x) for x in s.split('|')]

def is_separator_row(cells:list[str])->bool:
    """Return whether a Markdown row is only a table separator."""
    return bool(cells) and all((not c) or re.fullmatch(r':?-{3,}:?',c) for c in cells)

def unit_column_indexes(headers:list[str])->list[int]:
    """Return indexes of columns whose headers describe organizational units."""
    out=[]
    for i,h in enumerate(headers):
        h=_norm(h)
        if UNIT_COLUMN_HEADER_RE.fullmatch(h):
            out.append(i)
    return out

def clean_unit_value(v:str)->str:
    """Normalize and validate an organizational-unit cell value."""
    s=_norm(v)
    if not s:
        return ''
    if UNIT_COLUMN_HEADER_LIKE_RE.search(s):
        return ''
    if UNIT_COLUMN_MONEY_RE.fullmatch(s):
        return ''
    return s

def document_unit_row_map(doc:str):
    """
    Return raw-row-like normalized key -> organizational unit based on explicit
    table-header semantics. Works even when cell itself is just "Neurologiczna",
    "POZ", "Ch. dzieci", etc.
    """
    out={}
    headers=None
    unit_idxs=[]
    for line in str(doc or '').splitlines():
        cells=split_markdown_row(line)
        if not cells:
            continue

        # Detect a header row by explicit unit-column labels.
        idxs=unit_column_indexes(cells)
        if idxs:
            headers=cells
            unit_idxs=idxs
            continue

        # Any new table header without a unit column resets old state.
        if any(UNIT_COLUMN_HEADER_LIKE_RE.search(c or '') for c in cells) and not any(
            re.fullmatch(r'\d+',c or '') for c in cells[:2]
        ):
            headers=cells
            unit_idxs=[]
            continue

        if headers is None or not unit_idxs:
            continue
        if is_separator_row(cells):
            continue
        # OCR often drops trailing empty cells. Preserve semantic column
        # positions that still exist instead of requiring exact row width.
        if not (
            any(re.fullmatch(r'\d+',c) for c in cells[:2])
            or any(UNIT_COLUMN_MONEY_RE.search(c or '') for c in cells)
        ):
            continue

        vals=[]
        for i in unit_idxs:
            if i < len(cells):
                u=clean_unit_value(cells[i])
                if u:
                    vals.append(u)
        if not vals:
            continue

        # Preserve multiple unit columns if present, but avoid duplicates.
        vals=list(dict.fromkeys(vals))
        unit='; '.join(vals)
        key=' | '.join(cells)
        out[key]=unit
    return out

def section_unit_map(doc:str):
    """
    Stateful plain-text/OCR section parser:
      Oddział Chorób wewnętrznych:
      1. lekarz ...
      2. lekarz ...
    The current unit persists until another unit heading.
    Returns exact/normalized salary-line -> unit.
    """
    out={}
    current=''
    for line in str(doc or '').splitlines():
        raw=line.strip()
        s=_norm(raw)
        if not s:
            continue

        m=UNIT_COLUMN_SECTION_HEADING_RE.fullmatch(s)
        if m:
            current=_norm(m.group('unit'))
            continue

        if current and UNIT_COLUMN_SALARY_ITEM_RE.search(s):
            out[s]=current
            continue

        # Strong boundary: new unrelated table/title can end current section.
        if current and re.search(
            r'(?i)^(?:za[łl][ąa]cznik|zestawienie|wykaz|lista|'
            r'wynagrodzeni\w+|lp\.?\s*[|;])\b',s
        ):
            current=''
    return out

def inline_ocr_section_unit(raw_row:str)->Optional[str]:
    """
    Recover OCR cases where a true section heading is glued into a previous row,
    e.g. "... 178 579,57 Oddział Pediatryczny: 1. lekarz ...".
    Require a capitalized organizational heading; this avoids matching the
    phrase "asystent oddziału".
    """
    s=_norm(raw_row)
    matches=list(re.finditer(
        r'\b(?P<unit>(?:Oddział|Pododdział|Klinika|Pracownia|Poradnia|'
        r'Izba Przyjęć|Zakład|Ośrodek|SOR)'
        r'[^:]{0,140}):\s*'
        r'(?P<item>\d+\.\s*(?:lekarz|lek\.?|specjalista|asystent|rezydent))',
        s
    ))
    if matches:
        return _norm(matches[-1].group('unit'))
    return None

def document_unit_index_amount_map(doc:str):
    """
    Robust provenance map keyed by (row index, salary amount).
    This survives OCR dropping trailing empty cells and parser-normalized raw rows.

    Header state is reset by every new table header, preventing a unit column
    from leaking into a later unrelated table.
    """
    out={}
    headers=None
    unit_idxs=[]

    for line in str(doc or '').splitlines():
        cells=split_markdown_row(line)
        if not cells:
            continue
        if is_separator_row(cells):
            continue

        idxs=unit_column_indexes(cells)
        headerish=any(UNIT_COLUMN_HEADER_LIKE_RE.search(c or '') for c in cells)

        if idxs:
            headers=cells
            unit_idxs=idxs
            continue

        # A new header without an organizational-unit column closes the old schema.
        if headerish and not any(re.fullmatch(r'\d+',c or '') for c in cells[:2]):
            headers=cells
            unit_idxs=[]
            continue

        if not unit_idxs:
            continue

        # Numeric Lp is normally the first cell.
        idx=None
        for c in cells[:2]:
            if re.fullmatch(r'\d+',c or ''):
                idx=int(c)
                break
        if idx is None:
            continue

        amounts=[_money_value(c) for c in cells]
        amounts=[a for a in amounts if a is not None]
        if not amounts:
            continue
        # These salary tables contain one populated remuneration bucket per row.
        amount=max(amounts,key=abs)

        vals=[]
        for i in unit_idxs:
            if i < len(cells):
                u=clean_unit_value(cells[i])
                if u:
                    vals.append(u)
        if not vals:
            continue
        unit='; '.join(dict.fromkeys(vals))
        out[(idx,int(round(amount*100)))]=unit

    return out

def shifted_row_unit_candidate(raw_row:str):
    """
    For synthetic continuation rows produced from a source row with two salary
    amounts, preserve the single textual assignment carried by that source row.
    Only activates on explicit `shifted_to_next_lp` provenance.
    """
    s=str(raw_row or '')
    if 'shifted_to_next_lp' not in s:
        return ''
    cells=[_norm(x) for x in s.strip().strip('|').split('|')]
    vals=[]
    for c in cells:
        if not c or c=='shifted_to_next_lp':
            continue
        if re.fullmatch(r'\d+',c):
            continue
        if _money_value(c) is not None:
            continue
        if UNIT_COLUMN_HEADER_LIKE_RE.search(c):
            continue
        vals.append(c)
    vals=list(dict.fromkeys(vals))
    return vals[0] if len(vals)==1 else ''

def _norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

def _money_value(cell):
    s=str(cell or '').replace('\xa0',' ').strip()
    m=re.search(r'-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})|-?\d{4,9}(?:[,.]\d{2})',s)
    if not m:
        return None
    t=m.group(0).replace(' ','')
    if ',' in t:
        t=t.replace('.','').replace(',','.')
    try:
        return round(float(t),2)
    except ValueError:
        return None

