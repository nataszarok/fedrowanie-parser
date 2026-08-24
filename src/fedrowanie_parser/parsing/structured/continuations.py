"""Continuations parser family."""
from __future__ import annotations

import re

from typing import Optional

from ...models import SalaryRow
from ...processing.normalization import (
    norm_space,
    parse_money,
    money_values,
    detect_contract,
    split_markdown_row,
    split_md_row,
    is_separator_row,
)

__all__ = [
    "page_context_contract",
    "parse_indexed_three_col_continuation",
    "parse_indexed_single_salary_markdown",
    "parse_indexed_total_gross_continuation",
    "parse_salary_bracket_index_table",
    "parse_parallel_index_amount_columns",
    "parse_vertical_idx_code_gross_net",
]



def page_context_contract(lines: list[str], pos: int, fallback: str='') -> str:
    """Infer the local contract context for a row from nearby page lines."""
    chunk = '\n'.join(lines[max(0, pos - 12):pos + 1])
    return detect_contract(chunk, fallback)

def parse_indexed_three_col_continuation(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='') -> list[SalaryRow]:
    """Parse indexed three col continuation layouts into salary-row candidates."""
    candidates = []
    for raw in page.splitlines():
        if not raw.strip().startswith('|') or re.fullmatch('\\s*\\|?\\s*:?-{3,}:?\\s*(?:\\|\\s*:?-{3,}:?\\s*)+\\|?\\s*', raw):
            continue
        cells = split_markdown_row(raw)
        if len(cells) != 3:
            continue
        idx_txt = norm_space(cells[0]).strip('* ')
        mid = norm_space(cells[1]).strip('* ')
        valtxt = norm_space(cells[2]).strip('* ')
        if not re.fullmatch('\\d{1,4}[.)]?', idx_txt):
            continue
        if not mid or re.search('(?i)lp\\.?|razem|suma|ogółem|wynagrodzen', mid):
            continue
        vals = money_values(valtxt)
        if len(vals) != 1 or vals[0] <= 0:
            continue
        candidates.append((int(re.sub('\\D', '', idx_txt)), mid, vals[0], norm_space(raw)))
    if len(candidates) < 3:
        return []
    rows = []
    for idx, mid, val, raw in candidates:
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', mid, inherited_contract, None, val, page_no, 'markdown-3col-continuation', 'wysoka', raw))
    return rows

def parse_indexed_single_salary_markdown(case_pk, institution_pk, placowka, page_no, page):
    """Parse indexed single salary markdown layouts into salary-row candidates."""
    out = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith('|'):
            continue
        cc = split_md_row(raw)
        if len(cc) < 3 or is_separator_row(cc):
            continue
        idx = norm_space(cc[0]).rstrip('.')
        if not re.fullmatch('\\d{1,4}', idx):
            continue
        vals = []
        for j, c in enumerate(cc[1:], 1):
            toks = re.findall('(?<!\\d)(\\d{1,3}(?:[ .]\\d{3})+(?:,\\d{2})?|\\d{4,7},\\d{2})(?!\\d)', norm_space(c))
            for tok in toks:
                v = parse_money(tok)
                if v is not None:
                    vals.append((j, v))
        if len(vals) != 1 or vals[0][1] <= 0:
            continue
        j, val = vals[0]
        name = norm_space(cc[1]) or f'Lekarz {idx}'
        spec = norm_space(cc[2]) if len(cc) > 3 and j != 2 else ''
        if re.search('(?i)razem|suma|ogółem', name):
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, name, spec, '', None, val, page_no, 'indexed-single-salary-md', 'wysoka', norm_space(raw)))
    return out if len(out) >= 1 else []

def parse_indexed_total_gross_continuation(case_pk, institution_pk, placowka, page_no, page):
    """Parse indexed total gross continuation layouts into salary-row candidates."""
    out = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith('|'):
            continue
        cc = split_md_row(raw)
        if len(cc) < 6 or is_separator_row(cc):
            continue
        idx = norm_space(cc[0]).rstrip('.')
        codecell = norm_space(cc[1])
        if not re.fullmatch('\\d{1,4}', idx):
            continue
        if not re.fullmatch('[A-Za-z]-?\\d{2,5}|[A-Za-z0-9/_-]{3,20}', codecell):
            continue
        lastvals = money_values(cc[-1])
        if len(lastvals) != 1 or lastvals[0] <= 0:
            continue
        spec = norm_space(cc[2])
        out.append(SalaryRow(case_pk, institution_pk, placowka, codecell, spec, '', None, lastvals[0], page_no, 'indexed-total-gross-continuation', 'wysoka', norm_space(raw)))
    return out

def parse_salary_bracket_index_table(case_pk, institution_pk, placowka, page_no, page, full_doc):
    """Parse salary bracket index table layouts into salary-row candidates."""
    if not (
        re.search(r"(?i)<\s*500[ .]?000", full_doc)
        and re.search(r"(?i)>\s*500[ .]?000", full_doc)
        and re.search(r"(?i)>\s*1[ .]?000[ .]?000", full_doc)
    ):
        return []

    parsed = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith("|"):
            continue
        cc = split_md_row(raw)
        if len(cc) < 3 or is_separator_row(cc):
            continue

        idx = norm_space(cc[0]).rstrip(".")
        if not re.fullmatch(r"\d{1,4}", idx):
            continue

        spec = norm_space(cc[1])
        if not spec:
            continue

        vals = []
        for c in cc[2:]:
            vals.extend([v for v in money_values(c) if v > 0])

        parsed.append((int(idx), spec, vals, norm_space(raw)))

    if len(parsed) < 2:
        return []

    by_idx = {x[0]: x for x in parsed}
    out = []
    consumed = set()

    for idx, spec, vals, raw in parsed:
        if idx in consumed:
            continue

        # Normalny przypadek: jeden lekarz, jedna kwota w jednym koszyku.
        if len(vals) == 1:
            out.append(SalaryRow(
                case_pk, institution_pk, placowka,
                f"Lekarz {idx}", spec, "kontrakt/cywilnoprawna",
                None, vals[0], page_no,
                "salary-bracket-index", "wysoka", raw
            ))
            continue

        # OCR shift: dwa wynagrodzenia w wierszu N, następny wiersz N+1 pusty.
        if len(vals) == 2:
            nxt = by_idx.get(idx + 1)
            if nxt and len(nxt[2]) == 0:
                out.append(SalaryRow(
                    case_pk, institution_pk, placowka,
                    f"Lekarz {idx}", spec, "kontrakt/cywilnoprawna",
                    None, vals[0], page_no,
                    "salary-bracket-index", "wysoka", raw
                ))
                out.append(SalaryRow(
                    case_pk, institution_pk, placowka,
                    f"Lekarz {idx + 1}", nxt[1], "kontrakt/cywilnoprawna",
                    None, vals[1], page_no,
                    "salary-bracket-index", "wysoka",
                    raw + " | shifted_to_next_lp"
                ))
                consumed.add(idx + 1)

    return out

def parse_parallel_index_amount_columns(case_pk, institution_pk, placowka, page_no, page):
    """Parse parallel index amount columns layouts into salary-row candidates."""
    out = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith('|'):
            continue
        cc = split_md_row(raw)
        if len(cc) != 4 or is_separator_row(cc):
            continue
        i1 = re.fullmatch('\\d{1,4}', norm_space(cc[0]))
        i2 = re.fullmatch('\\d{1,4}', norm_space(cc[2])) if norm_space(cc[2]) else None
        c1 = norm_space(cc[1])
        c3 = norm_space(cc[3])
        money_only = re.compile('^\\s*(?:\\d{1,3}(?:[ .]\\d{3})+|\\d{4,7})(?:,\\d{1,2})?\\s*(?:zł)?\\s*$', re.I)
        a = money_values(c1) if money_only.fullmatch(c1) else []
        b = money_values(c3) if money_only.fullmatch(c3) else []
        if i1 and len(a) == 1 and (a[0] >= 1000):
            out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {i1.group()}', '', '', None, a[0], page_no, 'parallel-index-amount', 'wysoka', norm_space(raw)))
        if i2 and len(b) == 1 and (b[0] >= 1000):
            out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {i2.group()}', '', '', None, b[0], page_no, 'parallel-index-amount', 'wysoka', norm_space(raw)))
    idx = []
    for r in out:
        m = re.search('(\\d+)$', r.nazwa)
        idx.append(int(m.group(1)) if m else -1)
    return out if len(out) >= 10 and len(set(idx)) == len(idx) else []

def parse_vertical_idx_code_gross_net(case_pk, institution_pk, placowka, page_no, page):
    """Parse vertical idx code gross net layouts into salary-row candidates."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i < len(lines) - 2:
        m = re.match('^(\\d{1,4})\\s+([A-Za-z0-9/.-]{2,30})$', lines[i])
        if m:
            a = money_values(lines[i + 1])
            b = money_values(lines[i + 2])
            if len(a) == 1 and len(b) == 1 and (a[0] > 0):
                out.append(SalaryRow(case_pk, institution_pk, placowka, m.group(2), '', '', b[0], a[0], page_no, 'vertical-idx-code-gross-net', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 3 else []


