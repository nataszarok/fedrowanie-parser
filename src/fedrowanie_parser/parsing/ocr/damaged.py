"""Damaged parser family."""
from __future__ import annotations

import re

from typing import Optional

from ...models import SalaryRow
from ...processing.normalization import (
    norm_space,
    parse_money,
    money_cells,
)
from ...processing.document import is_metadata_context

__all__ = [
    "parse_ocr_contract_amount_list",
    "parse_ocr_broken_numbered_salary_table",
    "parse_forma_name_amount_ocr",
    "parse_lekarz_inline_anon_list",
]



def parse_ocr_contract_amount_list(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str) -> list[SalaryRow]:
    """Parse ocr contract amount list layouts into salary-row candidates."""
    rows = []
    seen_raw = set()
    for line in page.splitlines():
        raw = norm_space(line)
        if not raw or raw in seen_raw:
            continue
        seen_raw.add(raw)
        is_business = bool(re.search('(?i)gospodarcza', raw))
        is_civil = bool(re.search('(?i)(?:cywilno|qwilno|cwilno|ewiino|wiino).?prawna|umowa.{0,20}prawna', raw))
        if not (is_business or is_civil):
            continue
        amount_source = re.sub('(?<=\\d)-(?=\\d{3}[,.]\\d{2}\\b)', ' ', raw)
        toks = re.findall('(?<!\\d)(\\d{1,7}(?:[ .]\\d{3})*(?:,\\d{2})|\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2}))(?!\\d)', amount_source)
        if not toks:
            continue
        tok = toks[-1]
        val = parse_money(tok)
        if val is None or val <= 0:
            continue
        contract = 'działalność gospodarcza' if is_business else 'umowa cywilnoprawna'
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {len(rows) + 1}', '', contract, None, val, page_no, 'ocr-contract-amount-list', 'średnia', raw))
    if len(rows) < 10:
        return []
    out = []
    prev = None
    for r in rows:
        key = (r.typ_umowy, round(r.brutto or 0, 2))
        if key == prev:
            continue
        out.append(r)
        prev = key
    for i, r in enumerate(out, 1):
        r.nazwa = f'Lekarz {i}'
    return out

def parse_ocr_broken_numbered_salary_table(case_pk, institution_pk, placowka, page_no, page):
    """Parse ocr broken numbered salary table layouts into salary-row candidates."""
    if not re.search(r'(?i)oznaczenie\s+lekarza', page):
        return []
    if not re.search(r'(?is)roczne\s+wynagrodzenie.{0,120}(?:zł|nfz|2025)', page):
        return []

    explicit=[]
    # Flexible OCR: Lekarz nr 10 | 116 370; Lekarznr12 _ | 235 955
    exp_re=re.compile(
        r'(?i)lekarz\s*nr\s*(\d{1,3})\b.{0,18}?'
        r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})?',
        re.S
    )
    for m in exp_re.finditer(page):
        val=parse_money(m.group(2))
        if val is not None and val>=1000:
            explicit.append((int(m.group(1)), val, m.start(), norm_space(m.group(0))))
    if len(explicit)<3:
        return []
    explicit.sort()
    ids=[x[0] for x in explicit]
    if ids != list(range(ids[0], ids[0]+len(ids))):
        return []
    anchor_idx=ids[0]
    if anchor_idx<=2:
        return []
    anchor_pos=min(x[2] for x in explicit)

    # Only money-only lines between the salary header and the first explicit doctor label.
    hm=re.search(r'(?is)roczne\s+wynagrodzenie.{0,160}(?:zł|nfz)', page)
    start=hm.end() if hm else re.search(r'(?i)oznaczenie\s+lekarza',page).end()
    prefix=page[start:anchor_pos]
    prior=[]
    for raw in prefix.splitlines():
        line=norm_space(raw).strip('|_ ')
        if not line:
            continue
        # tolerate trailing OCR junk such as 's' or '|', but not ordinary prose.
        m=re.fullmatch(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})?\s*[A-Za-z|_]?', line)
        if not m:
            continue
        tok=re.match(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})?',line).group(0)
        val=parse_money(tok)
        if val is not None and val>=1000 and val != 2025:
            prior.append((val,norm_space(raw)))

    expected=anchor_idx-1
    # Exact sequence, or exactly one OCR-lost salary before the anchor.
    if len(prior) not in (expected, expected-1):
        return []
    missing=[] if len(prior)==expected else [len(prior)+1]
    comment='Rekonstrukcja z uszkodzonego OCR.'
    if missing:
        comment += f" Brak odczytywalnej kwoty dla Lekarz {missing[0]}; nie utworzono tego rekordu."

    out=[]
    for idx,(val,raw) in enumerate(prior,1):
        out.append(SalaryRow(case_pk,institution_pk,placowka,f'Lekarz {idx}','','',
                             None,val,page_no,'ocr-broken-numbered-table','średnia',raw,comment))
    for idx,val,_,raw in explicit:
        out.append(SalaryRow(case_pk,institution_pk,placowka,f'Lekarz {idx}','','',
                             None,val,page_no,'ocr-broken-numbered-table','średnia',raw,comment))
    return out

def parse_forma_name_amount_ocr(case_pk, institution_pk, placowka, page_no, page):
    """Parse forma name amount ocr layouts into salary-row candidates."""
    if not (re.search(r'(?m)^FORMA\s*$',page) or re.search(r'(?m)^FORMA\s+[A-ZĄĆĘŁŃÓŚŹŻ]',page)):
        return []
    start=re.search(r'(?m)^FORMA\b',page)
    block=page[start.start():] if start else page
    out=[]
    for raw in block.splitlines():
        line=norm_space(raw)
        if line=='FORMA': continue
        cells=money_cells(line)
        if not cells: continue
        prev=0
        for tok,val in cells:
            pos=line.find(tok,prev)
            label=norm_space(line[prev:pos].strip(' -–—|'))
            label=re.sub(r'(?i)^FORMA\s+','',label).strip()
            prev=pos+len(tok)
            # A later bare OCR number has no alphabetic label and is ignored.
            if not label or not re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]',label): continue
            if is_metadata_context(label) or val<=0 or val>5_000_000: continue
            if re.search(r'(?i)kierownik\s+dzia[łl]u|koniec\s+strony',label): continue
            out.append(SalaryRow(case_pk,institution_pk,placowka,label,'','',None,val,page_no,
                                 'forma-name-amount-ocr','średnia',line))
    return out if len(out)>=5 else []

def parse_lekarz_inline_anon_list(case_pk, institution_pk, placowka, page_no, page):
    """Parse lekarz inline anon list layouts into salary-row candidates."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    rows = []
    numbered = []
    first_unnum = None
    for raw in lines:
        m = re.fullmatch('(?i)Lekarz\\s+(\\d{1,4})\\s*(?:\\||[-–—])?\\s*(\\d[\\d .]*,\\d{2})', raw)
        if m:
            val = parse_money(m.group(2))
            if val and val > 0:
                numbered.append((int(m.group(1)), val, raw))
            continue
        m0 = re.fullmatch('(?i)Lekarz\\s*\\|\\s*(\\d[\\d .]*,\\d{2})', raw)
        if m0:
            val = parse_money(m0.group(1))
            if val and val > 0:
                first_unnum = (val, raw)
    if len(numbered) < 5:
        return []
    ids = {x[0] for x in numbered}
    if first_unnum and 2 in ids and (1 not in ids):
        rows.append(SalaryRow(case_pk, institution_pk, placowka, 'Lekarz 1', '', '', None, first_unnum[0], page_no, 'anon-lekarz-inline-list', 'wysoka', first_unnum[1]))
    for idx, val, raw in numbered:
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', '', '', None, val, page_no, 'anon-lekarz-inline-list', 'wysoka', raw))
    return rows


