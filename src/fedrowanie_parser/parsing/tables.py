"""Structured Markdown/OCR table parsers."""
from __future__ import annotations
from typing import Optional
from ..models import SalaryRow
from ..processing.normalization import *

def parse_markdown_tables(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='', inherited_kind: str='brutto', inherited_spec: str='') -> list[SalaryRow]:
    """Parse structured salary tables while preserving column semantics and provenance."""
    lines = page.splitlines()
    rows: list[SalaryRow] = []
    i = 0
    current_contract = detect_contract(page[:1500], inherited_contract)
    while i < len(lines):
        line = lines[i]
        cells = split_markdown_row(line)
        if len(cells) < 2 or i + 1 >= len(lines):
            current_contract = detect_contract(line, current_contract)
            i += 1
            continue
        sep = split_markdown_row(lines[i + 1])
        if len(sep) != len(cells) or not is_separator_row(sep):
            current_contract = detect_contract(line, current_contract)
            i += 1
            continue
        headers = cells
        headers_clean = [clean_header(x) for x in headers]
        semantic_lp, semantic_amount, semantic_person = semantic_annual_salary_columns(headers)
        table_context = '\n'.join(lines[max(0, i - 12):i + 2])
        exclude_table, _exclude_reason = table_should_be_excluded(headers, table_context)
        if exclude_table:
            i += 2
            while i < len(lines):
                rc = split_markdown_row(lines[i])
                if len(rc) < 2:
                    break
                if i + 1 < len(lines):
                    nxt = split_markdown_row(lines[i + 1])
                    if len(nxt) == len(rc) and is_separator_row(nxt):
                        break
                i += 1
            continue
        if not header_has_money_context(headers_clean):
            i += 2
            continue
        table_contract = detect_contract(' '.join(headers), current_contract)
        i += 2
        # Some PDFs have a two-row header, e.g.:
        # | UMOWY O PRACĘ | UMOWY ZLECENIA | KONTRAKT |
        # | wynagrodzenie brutto | wynagrodzenie brutto | wynagrodzenie brutto |
        if expand_stacked_contract_headers is not None and i < len(lines):
            first_cells = split_markdown_row(lines[i])
            effective, consumed = expand_stacked_contract_headers(headers_clean, first_cells)
            if consumed:
                headers_clean = effective
                i += 1
        while i < len(lines):
            raw = lines[i]
            rcells = split_markdown_row(raw)
            if len(rcells) < 2:
                break
            if is_separator_row(rcells):
                i += 1
                continue
            if i + 1 < len(lines):
                maybe_sep = split_markdown_row(lines[i + 1])
                if len(maybe_sep) == len(rcells) and is_separator_row(maybe_sep):
                    break
            if len(rcells) < len(headers):
                rcells += [''] * (len(headers) - len(rcells))
            elif len(rcells) > len(headers):
                rcells = rcells[:len(headers)]
            raw_clean = norm_space(raw)
            if is_metadata_or_date(raw_clean) or mentions_other_year(raw_clean) or is_summary_row(raw_clean):
                i += 1
                continue
            idx, idx_col = parse_idx(rcells, headers_clean)
            name, spec = infer_name_and_spec(rcells, headers_clean, idx_col)
            for c in rcells:
                m_doctor = re.fullmatch('(?i)lekarz\\s+(\\d{1,4})', norm_space(c))
                if m_doctor:
                    name = f'Lekarz {int(m_doctor.group(1))}'
                    break
            row_contract = detect_contract(' '.join(rcells), table_contract)
            candidates = []
            for col, (cell, h) in enumerate(zip(rcells, headers_clean)):
                if col == idx_col or not cell:
                    continue
                vals = money_cells(cell)
                if not vals:
                    continue
                financial_h = bool(re.search('(?i)wynagrod|kwota|brutto|netto|zł|pln|<|>|500|mln|milion|umow|kontrakt|zlecen', h))
                if not financial_h and h and re.search('(?i)rok|2025', h):
                    financial_h = True
                if not financial_h and h:
                    continue
                for tok, val in vals:
                    if 1900 <= val <= 2100 and re.fullmatch('20\\d{2}(?:,0+)?', tok.strip().replace('zł', '').strip()):
                        continue
                    candidates.append((col, h, tok, val))
            if not candidates:
                i += 1
                continue
            paid_2025 = [(col, h, tok, val) for col, h, tok, val in candidates if re.search('(?i)wynagrodzen(?:ie|ia).*wypłacone.*2025|wyplacone.*2025', h)]
            if paid_2025:
                _, _, _, paid_val = paid_2025[-1]
                rows.append(SalaryRow(case_pk, institution_pk, placowka, label_for_row(idx, name), spec, row_contract, None, paid_val, page_no, 'markdown-paid-2025', 'wysoka', raw_clean))
                i += 1
                continue
            total_gross = [(col, h, tok, val) for col, h, tok, val in candidates if re.search('(?i)łącznie.*brutto|lacznie.*brutto', h)]
            if total_gross:
                _, _, _, total_val = total_gross[-1]
                inferred = infer_contract_from_multi_columns(headers_clean, rcells) if infer_contract_from_multi_columns is not None else None
                total_contract = inferred['contract_type'] if inferred else row_contract
                rows.append(SalaryRow(case_pk, institution_pk, placowka, label_for_row(idx, name), spec, total_contract, None, total_val, page_no, 'markdown-total-gross', 'wysoka', raw_clean))
                i += 1
                continue
            # Separate contract-specific amount columns take precedence over the
            # generic net/gross heuristic. This prevents a multi-column table
            # from being collapsed into one arbitrary amount/type.
            split_contracts = split_multi_contract_amounts(headers_clean, rcells) if split_multi_contract_amounts is not None else []
            if split_contracts:
                for ct, val in split_contracts:
                    rows.append(SalaryRow(case_pk, institution_pk, placowka, label_for_row(idx, name), spec, ct, None, val, page_no, 'markdown-multi-contract', 'wysoka', raw_clean))
                i += 1
                continue

            net_val = gross_val = None
            emitted_multi_contract = False
            for col, h, tok, val in candidates:
                if 'netto' in h:
                    net_val = val
                elif 'brutto' in h:
                    gross_val = val
            if net_val is not None or gross_val is not None:
                if gross_val is None and net_val is None:
                    pass
                else:
                    rows.append(SalaryRow(case_pk, institution_pk, placowka, label_for_row(idx, name), spec, row_contract, net_val, gross_val, page_no, 'markdown-net-gross', 'wysoka', raw_clean))
                    i += 1
                    continue
            contract_candidates = []
            for col, h, tok, val in candidates:
                ct = detect_contract(h)
                if ct:
                    contract_candidates.append((ct, val))
            if contract_candidates:
                for ct, val in contract_candidates:
                    rows.append(SalaryRow(case_pk, institution_pk, placowka, label_for_row(idx, name), spec, ct, None, val, page_no, 'markdown-multi-contract', 'wysoka', raw_clean))
                i += 1
                continue
            vals = [x[3] for x in candidates]
            chosen = max(vals)
            kind = amount_kind(' '.join(headers))
            rows.append(SalaryRow(case_pk, institution_pk, placowka, label_for_row(idx, name), spec, row_contract, chosen if kind == 'netto' else None, chosen if kind == 'brutto' else None, page_no, 'markdown-table', 'wysoka', raw_clean))
            i += 1
        continue
    existing_raw = {norm_space(r.raw_row) for r in rows}
    no_header_4col = re.compile('^\\|\\s*(?P<idx>\\d{1,4})[.)]?\\s*\\|\\s*(?P<label>[^|]+?)\\s*\\|\\s*(?P<contract>[^|]+?)\\s*\\|\\s*(?P<amount>\\d{1,3}(?:[ .]\\d{3})*(?:[,.]\\d{1,2})|\\d{4,7}(?:[,.]\\d{1,2}))\\s*(?:zł)?\\s*\\|?\\s*$', re.I)
    current_section = inherited_spec
    for raw in lines:
        rc = norm_space(raw)
        if raw.lstrip().startswith('|'):
            m = no_header_4col.match(raw.strip())
            if not m:
                continue
            if rc in existing_raw or is_summary_row(rc) or is_metadata_or_date(rc) or mentions_other_year(rc):
                continue
            ct = detect_contract(m.group('contract'))
            if not ct:
                continue
            val = parse_money(m.group('amount'))
            if val is None:
                continue
            idx = int(m.group('idx'))
            label = norm_space(m.group('label'))
            generic = bool(re.match('(?i)^(?:lekarz|specjalista)\\b', label))
            name = f'Lekarz {idx}' if generic else label
            spec = current_section
            if generic:
                spec = f'{current_section} — {label}' if current_section else label
            rows.append(SalaryRow(case_pk, institution_pk, placowka, name, spec, ct, None, val, page_no, 'markdown-no-header-4col', 'wysoka', rc))
            existing_raw.add(rc)
            continue
        if re.search('(?i)\\b(?:ODDZIAŁ|PRACOWNIA|PORADNIA|NOCNA\\s+I\\s+ŚWIĄTECZNA\\s+OPIEKA)\\b', rc):
            current_section = rc
    existing_raw = {norm_space(r.raw_row) for r in rows}
    direct = re.compile('^\\|\\s*(?P<idx>\\d{1,4})\\s*\\|\\s*(?P<amount>\\d{1,3}(?:[ .]\\d{3})*(?:[,.]\\d{1,2})?)\\s*(?:zł)?\\s*\\|\\s*(?P<label>[^|]*)\\|?\\s*$', re.I)
    for raw in lines:
        rc = norm_space(raw)
        if rc in existing_raw or is_summary_row(rc) or is_metadata_or_date(rc) or mentions_other_year(rc):
            continue
        m = direct.match(raw.strip())
        if not m:
            continue
        val = parse_money(m.group('amount'))
        if val is None:
            continue
        idx = int(m.group('idx'))
        label = norm_space(m.group('label'))
        if label and (not re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', label)):
            continue
        spec = label or inherited_spec
        kind = inherited_kind
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', spec, current_contract, val if kind == 'netto' else None, val if kind == 'brutto' else None, page_no, 'markdown-continuation', 'wysoka', rc))
    existing_raw = {norm_space(r.raw_row) for r in rows}
    section_contract = inherited_contract
    for raw in lines:
        rc = norm_space(raw)
        detected = detect_contract(rc)
        if detected:
            section_contract = detected
        if not raw.lstrip().startswith('|'):
            continue
        cells2 = split_md_row(raw)
        if len(cells2) != 2 or is_separator_row(cells2):
            continue
        label, valtxt = cells2
        vals = money_values(valtxt)
        if not label or len(vals) != 1 or rc in existing_raw or is_summary_row(rc):
            continue
        if vals[0] in (2024.0, 2025.0, 2026.0):
            continue
        rows.append(SalaryRow(case_pk, institution_pk, placowka, label, label, section_contract, None, vals[0], page_no, 'markdown-two-col-continuation', 'wysoka', rc))
        existing_raw.add(rc)
    for i, raw in enumerate(lines):
        ctx = ' '.join(lines[max(0, i - 8):i + 1]).lower()
        if not ('umow' in ctx and 'prac' in ctx and ('kontrakt' in ctx or 'cywilnopraw' in ctx)):
            continue
        if not raw.lstrip().startswith('|') or len(split_md_row(raw)) != 2:
            continue
        left_no = right_no = 0
        parallel_buf = []
        for raw2 in lines[i + 1:]:
            if not raw2.lstrip().startswith('|'):
                if raw2.strip():
                    break
                continue
            cc = split_md_row(raw2)
            if len(cc) != 2 or is_separator_row(cc):
                continue
            mv0, mv1 = (money_values(cc[0]), money_values(cc[1]))
            if not mv0 and (not mv1):
                continue
            parallel_buf.append((norm_space(raw2), mv0, mv1))
        monetary = [v for _, a, b in parallel_buf for v in a + b]
        if monetary and sum((v >= 1000 for v in monetary)) / len(monetary) >= 0.8:
            for rr, mv0, mv1 in parallel_buf:
                if mv0:
                    left_no += 1
                    rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz UoP {left_no}', '', 'umowa o pracę', None, mv0[0], page_no, 'markdown-parallel-money-columns', 'wysoka', rr))
                if mv1:
                    right_no += 1
                    rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz Kontrakt {right_no}', '', 'kontrakt/cywilnoprawna', None, mv1[0], page_no, 'markdown-parallel-money-columns', 'wysoka', rr))
        break
    existing_raw = {norm_space(r.raw_row) for r in rows}
    empty_lp = re.compile('^\\|\\s*\\|\\s*(?P<label>[^|]+?)\\s*\\|\\s*(?P<amount>\\d{1,3}(?:[ .]\\d{3})*(?:[,.]\\d{1,2})|\\d{4,7}(?:[,.]\\d{1,2}))\\s*(?:zł)?\\s*\\|?\\s*$', re.I)
    for raw in lines:
        m = empty_lp.match(raw.strip())
        if not m or norm_space(raw) in existing_raw or is_summary_row(raw):
            continue
        vals = money_cells(m.group('amount'))
        if vals and vals[0][1] > 0:
            rows.append(SalaryRow(case_pk, institution_pk, placowka, norm_space(m.group('label')), '', current_contract, None, vals[0][1], page_no, 'markdown-empty-lp', 'wysoka', norm_space(raw)))
    return rows

