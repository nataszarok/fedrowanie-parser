from __future__ import annotations
import re
from .money import parse_money
from .models import CellTable

_COUNT=re.compile(r'(?i)^\s*(?:count|liczba(?:\s+lekarzy|\s+wierszy)?)\s*:?\s*$')
_SUM=re.compile(r'(?i)^\s*(?:suma|razem)\s*:?\s*$')

def _right_numeric(row, i):
    for c in row[i+1:i+4]:
        v=parse_money(c)
        if v is not None: return v
    return None

def source_controls(tables: list[CellTable]) -> dict:
    counts=[]; sums=[]
    for t in tables:
        for row in t.rows:
            for i,c in enumerate(row):
                text=str(c or '').strip()
                if _COUNT.match(text):
                    v=_right_numeric(row,i)
                    if v is not None and 0 < v < 100000 and abs(v-round(v))<1e-6: counts.append(int(round(v)))
                elif _SUM.match(text):
                    v=_right_numeric(row,i)
                    if v is not None and v>=1000: sums.append(round(v,2))
    # preserve order, deduplicate exact repeats
    counts=list(dict.fromkeys(counts)); sums=list(dict.fromkeys(sums))
    return {'counts':counts,'gross_sums':sums}

def compare_controls(row_count: int, gross_sum: float, controls: dict) -> dict:
    counts=controls.get('counts',[]); sums=controls.get('gross_sums',[])
    count_match=None if not counts else (row_count in counts or sum(counts)==row_count)
    gross_match=None if not sums else (any(abs(gross_sum-x)<=0.02 for x in sums) or abs(gross_sum-sum(sums))<=0.02)
    return {'count_match':count_match,'gross_match':gross_match,'counts':counts,'gross_sums':sums}
