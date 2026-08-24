"""Vertical parser family."""
from __future__ import annotations

import re

from typing import Optional

from ...models import SalaryRow
from ...processing.normalization import (
    norm_space,
    parse_money,
    money_values,
    detect_contract,
)

__all__ = [
    "parse_vertical_label_amount_pairs",
    "parse_vertical_indexname_amount",
    "parse_vertical_index_code_label_amount",
    "parse_vertical_named_salary_table",
    "parse_vertical_role_named_amount",
    "parse_two_section_vertical_salary",
    "parse_numbered_amount_only_series",
    "parse_parallel_name_amount_lists",
    "parse_parallel_doctor_amount_lists",
    "parse_anonymous_amount_only_series",
]



def parse_vertical_label_amount_pairs(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='') -> list[SalaryRow]:
    """Parse vertical label amount pairs layouts into salary-row candidates."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    pairs = []
    for i in range(len(lines) - 1):
        label = lines[i]
        amount_line = lines[i + 1]
        if len(label) > 80 or re.fullmatch('[\\d\\s.,/-]+', label):
            continue
        if re.match('^\\d{1,4}[.)]?\\s+', label):
            continue
        if re.search('(?i)razem|suma|wynagrodzen|strona|dyrektor|telefon|nip|regon|krs|brutto|netto|stawka', label):
            continue
        if re.search('(?i)zł\\s*/|zł/mies|zł/godz', label):
            continue
        vals = money_values(amount_line)
        if len(vals) != 1:
            continue
        if not re.fullmatch('\\s*(?:\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})?\\s*(?:zł)?\\s*', amount_line, re.I):
            continue
        if vals[0] <= 0:
            continue
        pairs.append((label, vals[0], f'{label} | {amount_line}'))
    if len(pairs) < 5:
        return []
    return [SalaryRow(case_pk, institution_pk, placowka, label, '', inherited_contract, None, val, page_no, 'vertical-label-amount', 'wysoka', raw) for label, val, raw in pairs]

def parse_vertical_indexname_amount(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='') -> list[SalaryRow]:
    """Parse vertical indexname amount layouts into salary-row candidates."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    rows = []
    for i in range(len(lines) - 1):
        m = re.match('^(\\d{1,4})\\)?\\s+(.+)$', lines[i])
        if not m:
            continue
        name = norm_space(m.group(2))
        if not re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', name):
            continue
        nxt = lines[i + 1]
        nxt_money = re.sub('\\s+,', ',', nxt)
        vals = money_values(nxt_money)
        if len(vals) != 1:
            continue
        if not re.fullmatch('\\s*\\d[\\d ]*(?:\\s*,\\s*\\d{1,2})?\\s*(?:zł)?\\s*', nxt, re.I):
            continue
        val = vals[0]
        if val <= 0:
            continue
        rows.append(SalaryRow(case_pk, institution_pk, placowka, name, '', inherited_contract, None, val, page_no, 'vertical-index-name-amount', 'wysoka', f'{m.group(1)} {name} | {nxt}'))
    if len(rows) < 5:
        return []
    return rows

def parse_vertical_index_code_label_amount(case_pk, institution_pk, placowka, page_no, page):
    """Parse vertical index code label amount layouts into salary-row candidates."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i < len(lines) - 2:
        m = re.match('^(\\d{1,4})\\s+([A-Za-z0-9/.-]{3,20})$', lines[i])
        if m and i + 2 < len(lines):
            label = lines[i + 1]
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and re.search('(?i)lekarz|kontrakt|umow|kartotek|wynagrod|asystent|kierownik|stażysta|stazysta|rezydent', label):
                ct = detect_contract(label)
                out.append(SalaryRow(case_pk, institution_pk, placowka, m.group(2), label, ct, None, vals[0], page_no, 'vertical-index-code-label-amount', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        if re.fullmatch('\\d{1,4}', lines[i]) and i + 2 < len(lines):
            label = lines[i + 1]
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and re.search('(?i)lekarz|kontrakt|umow|kartotek|wynagrod|asystent|kierownik|stażysta|stazysta|rezydent', label):
                ct = detect_contract(label)
                out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {lines[i]}', label, ct, None, vals[0], page_no, 'vertical-index-code-label-amount', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 3 else []

def parse_vertical_named_salary_table(case_pk, institution_pk, placowka, page_no, page):
    """Parse vertical named salary table layouts into salary-row candidates."""
    if not (re.search('(?i)imię i nazwisko|imie i nazwisko', page) and re.search('(?i)kwota wynagrodzenia.*2025', page)):
        return []
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i + 2 < len(lines):
        if re.fullmatch('\\d{1,4}', lines[i]):
            name = lines[i + 1]
            vals = money_values(lines[i + 2])
            if re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', name) and len(vals) == 1 and (vals[0] > 0):
                out.append(SalaryRow(case_pk, institution_pk, placowka, name, '', '', None, vals[0], page_no, 'vertical-named-salary-table', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 3 else []

def parse_vertical_role_named_amount(case_pk, institution_pk, placowka, page_no, page):
    """Parse vertical role named amount layouts into salary-row candidates."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    role = ''
    i = 0
    stop_re = re.compile('(?i)^umowa\\b|^kontrakt\\b|^l\\.?p\\.?$|^wypłacone\\b|^nazwisko\\b')
    while i < len(lines):
        low = lines[i].lower()
        if low in {'ordynator', 'koordynator'}:
            role = low
            i += 1
            continue
        if role and stop_re.search(lines[i]):
            role = ''
            i += 1
            continue
        if role and re.fullmatch('\\d{1,3}', lines[i]):
            idx = lines[i]
            names = []
            j = i + 1
            found = False
            while j < len(lines) and len(names) < 3:
                if stop_re.search(lines[j]) or lines[j].lower() in {'ordynator', 'koordynator'}:
                    break
                vals = money_values(lines[j])
                if len(vals) == 1 and re.fullmatch('\\d[\\d ]*(?:,\\d{1,2})?', lines[j]):
                    name = norm_space(' '.join(names))
                    if name:
                        out.append(SalaryRow(case_pk, institution_pk, placowka, name, role, '', None, vals[0], page_no, 'vertical-role-named-amount', 'wysoka', f'{role} | {idx} | {name} | {lines[j]}'))
                    i = j + 1
                    found = True
                    break
                if re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', lines[j]):
                    names.append(lines[j])
                j += 1
            if found:
                continue
        i += 1
    return out

def parse_two_section_vertical_salary(case_pk, institution_pk, placowka, page_no, page):
    """Parse two section vertical salary layouts into salary-row candidates."""
    if not (re.search('(?i)wynagrodzenie lekarzy zatrudnionych', page) and re.search('(?i)umow[ęe] o prac[ęe]', page) and re.search('(?i)umow[ęe] cywilnoprawn', page)):
        return []
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i + 2 < len(lines):
        m = re.fullmatch('(?i)Lekarz\\s+(\\d{1,4})', lines[i])
        if m:
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and vals[0] > 0:
                out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {m.group(1)}', lines[i + 1], 'umowa o pracę', None, vals[0], page_no, 'two-section-vertical', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        idx = lines[i].rstrip('.')
        if re.fullmatch('\\d{1,4}', idx) and re.search('(?i)dyżur|dyzur|praca dzienna', lines[i + 1]):
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and vals[0] > 0:
                out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', lines[i + 1], 'umowa cywilnoprawna', None, vals[0], page_no, 'two-section-vertical', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 5 else []

def parse_numbered_amount_only_series(case_pk, institution_pk, placowka, page_no, page):
    """Parse numbered amount only series layouts into salary-row candidates."""
    m = re.search('(?is)wynagrodzenia.{0,160}(?:kształtowały|ksztaltowaly|następująco|nastepujaco)\\s*:\\s*(.+)', page)
    if not m:
        return []
    tail = m.group(1)
    pat = re.compile('(?<!\\d)(\\d{1,3})[.)]\\s*(\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})\\s*zł', re.I)
    out = []
    for mm in pat.finditer(tail):
        am = re.search('(\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})', mm.group(0))
        if not am:
            continue
        val = parse_money(am.group(0))
        if val is None or val <= 0:
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {mm.group(1)}', '', '', None, val, page_no, 'numbered-amount-only-series', 'wysoka', norm_space(mm.group(0))))
    return out if len(out) >= 5 else []

def parse_parallel_name_amount_lists(case_pk: int, institution_pk: Optional[int], placowka: str, doc: str) -> list[SalaryRow]:
    """Parse parallel name amount lists layouts into salary-row candidates."""
    text = norm_space(doc)
    m = re.search('(?is)imienna\\s+lista\\s+lekarzy.*?2025\\s*:?\\s*(.*?)łączne\\s+wynagrodzenie\\s+wypłacone\\s+w\\s*2025\\s*roku\\s*:?', text)
    if not m:
        return []
    names_blob = m.group(1).strip(' ,.;')
    after = text[m.end():]
    names = [norm_space(x) for x in names_blob.split(',') if norm_space(x)]
    amounts = []
    for mm in re.finditer('(?<!\\d)(\\d{1,3}(?:[ .]\\d{3})+(?:,\\d{1,2})|\\d{1,6},\\d{1,2})\\s*zł', after, re.I):
        val = parse_money(mm.group(1))
        if val is not None:
            amounts.append(val)
    if not names or len(names) != len(amounts):
        return []
    return [SalaryRow(case_pk, institution_pk, placowka, name, '', '', None, val, None, 'parallel-name-amount-lists', 'wysoka', f'{i}. {name} | {val:.2f}') for i, (name, val) in enumerate(zip(names, amounts), 1)]

def parse_parallel_doctor_amount_lists(case_pk, institution_pk, placowka, page_no, page):
    """Parse parallel doctor amount lists layouts into salary-row candidates."""
    m1=re.search(
        r'(?is)\bLekarze\s*:\s*(.+?)\bWynagrodzenia\s+lekarzy\s*:\s*(.+)',
        page
    )
    if not m1:
        return []

    names_part=m1.group(1)
    amounts_part=m1.group(2)

    raw_names=[norm_space(x).strip(" .") for x in re.split(r'[,;\n]+',names_part) if norm_space(x)]
    names=[]
    for x in raw_names:
        if re.search(r'(?i)z poważaniem|dyrektor|telefon|email|www\.|załącznik',x):
            break
        if re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]',x):
            names.append(x)

    # Odetnij stopkę po liście kwot.
    amounts_part=re.split(
        r'(?i)\n\s*(?:Pozdrawiam|Z poważaniem|Dyrektor|Prezes|Główny Specjalista)\b',
        amounts_part,maxsplit=1
    )[0]

    # Normalizacja "97.125, 00" oraz sklejenia "11.970,00425.910,00".
    s=re.sub(r',\s+(\d{2})(?=[;\s])',r',\1',amounts_part)
    s=re.sub(r'(,\d{2})(?=\d)',r'\1;',s)
    amount_parts=[norm_space(x) for x in re.split(r';|\n',s) if norm_space(x)]

    # Gdy kwot jest o 1 więcej, spróbuj bezpiecznie rozdzielić jedno sklejone nazwisko.
    if len(amount_parts)==len(names)+1:
        single_ratio=sum(1 for x in names if len(x.split())==1)/max(1,len(names))
        candidates=[
            (i,x) for i,x in enumerate(names)
            if len(x.split())==2
            and '-' not in x
            and all(re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+',w) for w in x.split())
        ]
        if single_ratio>=0.8 and len(candidates)==1:
            i,x=candidates[0]
            a,b=x.split()
            names=names[:i]+[a,b]+names[i+1:]

    if len(names)<3 or len(names)!=len(amount_parts):
        return []

    out=[]
    unreadable=[]
    for idx,(name,part) in enumerate(zip(names,amount_parts),1):
        # Kwota musi być pełnym tokenem; nie naprawiamy arbitralnie np. 43.37,73.
        mm=re.fullmatch(
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7}),(\d{2})\s*(?:zł)?[.,]?',
            part,re.I
        )
        if not mm:
            unreadable.append((idx,name,part))
            continue
        val=parse_money(mm.group(1)+','+mm.group(2))
        if val is None or val<=0:
            unreadable.append((idx,name,part))
            continue
        row=SalaryRow(
            case_pk,institution_pk,placowka,name,"","",
            None,val,page_no,"parallel-doctor-amount-lists","wysoka",
            f"{idx} | {name} | {part}"
        )
        out.append(row)

    # Wymagamy, aby prawie cała lista była czytelna.
    if len(out)<3 or len(out) < len(names)-2:
        return []
    if unreadable:
        note="; ".join(f"poz. {i}: {n} / {raw}" for i,n,raw in unreadable)
        for r in out:
            r.komentarz=(r.komentarz+"; " if r.komentarz else "") + \
                "Lista równoległa; pominięto nieczytelną pozycję OCR: " + note
    return out

def parse_anonymous_amount_only_series(case_pk, institution_pk, placowka, page_no, page):
    """Parse anonymous amount only series layouts into salary-row candidates."""
    if not re.search(r'(?i)\b(?:kwoty\s+brutto|kwoty\s+netto)\s*:', page):
        return []
    if not (re.search(r'(?i)lekarz',page) or re.search(r'(?i)wynagrodze[nń]',page)):
        return []

    # Bierz tylko fragment po nagłówku.
    m=re.search(r'(?is)\b(?:kwoty\s+brutto|kwoty\s+netto)\s*:\s*(.+)',page)
    if not m:
        return []
    tail=m.group(1)

    vals=[]
    raws=[]
    for line in tail.splitlines():
        raw=norm_space(line)
        if not raw:
            continue
        # przerwij na podpisie/stopce lub nowej sekcji tekstowej
        if re.search(r'(?i)^z poważaniem|^dyrektor\b|^prezes\b|^--$|^załącznik',raw):
            break
        mm=re.fullmatch(
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{2})\s*(?:zł)?[.,]?',
            raw,re.I
        )
        if not mm:
            # toleruj numerację "1. 182.685,60"
            mm=re.fullmatch(
                r'\d{1,3}[.)]\s*(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{2})\s*(?:zł)?[.,]?',
                raw,re.I
            )
        if not mm:
            continue
        am=re.search(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{2})',raw)
        if not am:
            continue
        val=parse_money(am.group(0))
        if val is not None and val>0:
            vals.append(val); raws.append(raw)

    if len(vals)<3:
        return []

    # Netto/brutto z nagłówka
    is_netto=bool(re.search(r'(?i)kwoty\s+netto',page))
    out=[]
    for idx,(val,raw) in enumerate(zip(vals,raws),1):
        out.append(SalaryRow(
            case_pk,institution_pk,placowka,f"Lekarz {idx}","","",
            val if is_netto else None,
            None if is_netto else val,
            page_no,"anonymous-amount-only-series","wysoka",raw
        ))
    return out


