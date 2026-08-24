"""Extraction orchestration and semantic enrichment."""
from __future__ import annotations
import re
import sqlite3
from .models import SalaryRow
from .constants import (
    GROSS_RE,
    NET_RE,
    PARSER_RANK,
    STRUCTURED_METADATA_PARSERS,
    YEAR,
)
from .services.case_extraction import validate_case_rows



__all__ = [
    "extract_all",
]

# Public package APIs are intentionally imported wholesale; each module defines __all__.
from .processing.api import *
from .parsing.tables import *
from .parsing.layouts import *
from .parsing.plain_text import *
from .enrichment.api import *
from .special_cases.api import *

def extract_all(con: sqlite3.Connection) -> list[SalaryRow]:
    """Extract normalized salary rows from all eligible cases in the source database."""
    con.row_factory = sqlite3.Row
    query = """
                SELECT cp.case_pk, cp.text, c.institution_pk,
                       COALESCE(i.name, c.name, '') AS institution_name
                FROM case_pages cp
                LEFT JOIN cases c ON c.pk = cp.case_pk
                LEFT JOIN institutions i ON i.pk = c.institution_pk
                WHERE cp.text IS NOT NULL AND TRIM(cp.text) <> ''
                ORDER BY cp.case_pk, cp.rowid

            """
    cases = {}
    for r in con.execute(query):
        b = cases.setdefault(r['case_pk'], [r['institution_pk'], r['institution_name'], []])
        b[2].append(r['text'] or '')
    accepted, statuses = ([], [])
    for case_pk, (institution_pk, placowka, parts) in cases.items():
        doc, meta = recipient_document('\n'.join(parts))
        if not meta['thread_detected']:
            statuses.append((case_pk, institution_pk, placowka, 'NO_SUBSTANTIVE_DATA_DETECTED', 'recipient_thread_not_detected', 0))
            continue
        if meta['substantive_recipient_messages'] == 0:
            statuses.append((case_pk, institution_pk, placowka, 'NO_SUBSTANTIVE_DATA_DETECTED', 'no_substantive_recipient_reply', 0))
            continue
        rows = _case_rows(case_pk, institution_pk, placowka, doc)
        comment = topn_comment(doc)
        if comment:
            for r in rows:
                r.komentarz = comment
        status, reason = correspondence_status(doc, rows)
        if status.startswith('INDIVIDUAL_ANNUAL_2025'):
            accepted.extend(rows)
        statuses.append((case_pk, institution_pk, placowka, status, reason, len(rows)))
    _store_case_status(con, statuses)
    return accepted

def _page_rows(case_pk, institution_pk, placowka, page_no, page, doc, inherited_contract, inherited_kind, inherited_spec):
    """Run the parser families applicable to one document page."""
    vals = money_values(page)
    if (vals and max(vals) < 1000
            and not re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', page)):
        return []
    if page_is_group_aggregate_salary_table(page):
        return []
    args = (case_pk, institution_pk, placowka, page_no, page)
    broken_ocr = parse_ocr_broken_numbered_salary_table(*args)
    if broken_ocr:
        return broken_ocr
    md = parse_markdown_tables(*args, inherited_contract, inherited_kind, inherited_spec)
    md_cont = parse_indexed_three_col_continuation(*args, inherited_contract)
    vertical_pairs = parse_vertical_label_amount_pairs(*args, inherited_contract)
    vertical_named = parse_vertical_indexname_amount(*args, inherited_contract)
    ocr_contract = parse_ocr_contract_amount_list(*args)
    named_inline = parse_numbered_named_inline_salary(*args)
    lekarz_inline = parse_lekarz_inline_salary(*args)
    vertical_struct = parse_vertical_index_code_label_amount(*args)
    gross_net_struct = parse_vertical_idx_code_gross_net(*args)
    parallel_idx = parse_parallel_index_amount_columns(*args)
    anon_inline = parse_lekarz_inline_anon_list(*args)
    indexed_single = parse_indexed_single_salary_markdown(*args)
    total_gross_cont = parse_indexed_total_gross_continuation(*args)
    bracket_rows = parse_salary_bracket_index_table(*args, doc)
    embedded_list = parse_embedded_numbered_salary_list(*args, doc)
    specialty_lines = parse_specialty_amount_lines(*args)
    role_named = parse_vertical_role_named_amount(*args)
    named_table = parse_vertical_named_salary_table(*args)
    two_section = parse_two_section_vertical_salary(*args)
    annual_prose = parse_explicit_annual_prose_salary(*args)
    amount_series = parse_numbered_amount_only_series(*args)
    body_lekarz = parse_body_lekarz_number_amount(*args)
    body_lp = parse_body_lp_amount(*args)
    parallel_lists = parse_parallel_doctor_amount_lists(*args)
    anon_amounts = parse_anonymous_amount_only_series(*args)
    annual_contract_lines = parse_annual_amount_contract_lines(*args)
    contract_practice_costs = parse_contract_practice_cost_list(*args)
    forma_rows = parse_forma_name_amount_ocr(*args)
    single_anon_annual = parse_single_anonymized_annual_amount(*args)
    named_colon_annual = parse_annual_named_colon_amount_list(*args)
    plain = parse_plain_lines(*args)
    existing_vertical = [r for r in plain if r.parser == 'plain-vertical']
    vertical_named = [r for r in vertical_named if not re.fullmatch('[\\d\\s.,]+\\s*zł', r.nazwa or '', re.I)]
    if existing_vertical:
        vertical_pairs = []
        plain = [r for r in plain if r.parser != 'plain-index-amount']
        if vertical_named and len(vertical_named) >= len(existing_vertical):
            plain = [r for r in plain if r.parser != 'plain-vertical']
        else:
            vertical_named = []
    elif vertical_pairs:
        plain = [r for r in plain if r.parser not in ('plain-index-amount', 'plain-inline')]
    if embedded_list:
        named_inline = []
    strong = named_inline or lekarz_inline or vertical_struct or gross_net_struct or parallel_idx or anon_inline or bracket_rows or embedded_list or amount_series or specialty_lines or role_named or named_table or two_section or annual_prose or body_lekarz or body_lp or parallel_lists or anon_amounts or annual_contract_lines or contract_practice_costs or forma_rows or single_anon_annual or named_colon_annual
    if named_table or two_section or annual_prose:
        plain = [r for r in plain if r.parser not in ('plain-inline', 'plain-index-amount', 'plain-vertical', 'plain-named')]
        vertical_pairs = []
    if strong:
        plain = [r for r in plain if r.parser not in ('plain-inline', 'plain-index-amount', 'plain-vertical')]
    groups = (md, md_cont, named_inline, lekarz_inline, vertical_struct, gross_net_struct, parallel_idx, anon_inline, indexed_single, total_gross_cont, bracket_rows, embedded_list, amount_series, specialty_lines, role_named, named_table, two_section, annual_prose, body_lekarz, body_lp, parallel_lists, anon_amounts, annual_contract_lines, contract_practice_costs, forma_rows, single_anon_annual, named_colon_annual, vertical_pairs, vertical_named, ocr_contract, plain)
    return [row for group in groups for row in group]

def _technical_filter(rows):
    """Parse or process the `_technical_filter` layout/stage."""
    out = []
    for r in deduplicate(rows):
        if suspicious_amount(r) or is_summary_row(r.raw_row):
            continue
        if is_metadata_or_date(r.raw_row) and r.parser not in STRUCTURED_METADATA_PARSERS:
            continue
        if re.search('(?i)<\\s*500[ .]?000|>\\s*500[ .]?000|>\\s*1[ .]?000[ .]?000', r.raw_row):
            continue
        if r.parser == 'markdown-table' and (r.brutto or r.netto or 0) < 1000 and re.search('(?i)okres:|od 01 do 12', r.raw_row):
            continue
        out.append(r)
    return out

def _rank_dedup(rows):
    """Parse or process the `_rank_dedup` layout/stage."""
    raw_best = {}
    for r in rows:
        raw = norm_space(r.raw_row).lower()
        indexed = bool(re.match('^\\|?\\s*\\d{1,4}\\s*[.):]?\\s*\\|', raw))
        key = (r.case_pk, None if indexed else r.strona, raw, r.netto, r.brutto)
        old = raw_best.get(key)
        if (
            old is None
            or ((r.typ_umowy or '').strip() and not (old.typ_umowy or '').strip())
            or (
                bool((r.typ_umowy or '').strip()) == bool((old.typ_umowy or '').strip())
                and PARSER_RANK.get(r.parser, 0) > PARSER_RANK.get(old.parser, 0)
            )
        ):
            raw_best[key] = r
    best = {}
    for r in raw_best.values():
        raw = norm_space(r.raw_row).lower()
        if re.match('^\\|?\\s*\\d{1,4}\\s*[.):]?\\s*\\|', raw):
            key = (r.case_pk, r.strona, raw, r.netto, r.brutto)
        else:
            key = (r.case_pk, r.strona, norm_space(r.nazwa).lower(), norm_space(r.specjalizacja).lower(), norm_space(r.typ_umowy).lower(), r.netto, r.brutto)
        old = best.get(key)
        if old is None or PARSER_RANK.get(r.parser, 0) > PARSER_RANK.get(old.parser, 0):
            best[key] = r
    return list(best.values())

def _case_rows(case_pk, institution_pk, placowka, doc):
    """Extract, reconcile and enrich salary rows for a single case."""
    if aggregate_count_total_guard(doc):
        return []
    parallel = parse_parallel_name_amount_lists(case_pk, institution_pk, placowka, doc)
    if parallel:
        return filter_registry_capital_false_rows(_rank_dedup(_technical_filter(parallel)), doc)

    rows = parse_section_state_rows(case_pk, institution_pk, placowka, doc)
    contract, kind, spec = ('', 'brutto', '')
    for page_no, page in split_pages(doc):
        if not page_is_2025_relevant(page, doc):
            continue
        head='\n'.join(page.splitlines()[:12])
        contract=detect_contract(head,contract)
        if NET_RE.search(head) and (not GROSS_RE.search(head)):
            kind='netto'
        elif GROSS_RE.search(head):
            kind='brutto'
        rows.extend(_page_rows(case_pk,institution_pk,placowka,page_no,page,doc,contract,kind,spec))

    base=_rank_dedup(_technical_filter(rows))

    # Importable monthly-ledger annualizer:
    # repeated rows `Data Dokumentu | Podmiot | Wartość` are transactions,
    # not annual salary rows. Sum every named recipient over 2025.
    ledger_rows=[]
    if parse_monthly_ledger is not None and aggregate_transactions is not None:
        txs=parse_monthly_ledger(doc, YEAR)
        # Conservative activation: a real ledger must be sizeable and span
        # multiple months. This prevents accidental activation on a small table.
        months={tx.date[3:5] for tx in txs}
        if len(txs)>=20 and len(months)>=3:
            annual=aggregate_transactions(txs)
            if merge_local_person_variants is not None:
                annual=merge_local_person_variants(annual)
            # In this document shape, plain-index-amount commonly interprets
            # page totals such as `1 960 801,29` as "Lekarz 1". Suppress only
            # this weak parser; keep independent annual UoP/zlecenie tables.
            base=[r for r in base if r.parser!='plain-index-amount']
            for a in annual:
                ledger_rows.append(SalaryRow(
                    case_pk,institution_pk,placowka,a.display_name,'','',
                    None,a.annual_total,0,'monthly-ledger-annualizer','wysoka',
                    f'{a.display_name} | suma 2025: {a.annual_total:.2f}',
                    f'suma z {a.tx_count} miesięcznych wpisów; miesiące={a.months_count}; '
                    f'typ_podmiotu={a.entity_kind}; źródło nie rozróżnia brutto/netto'
                ))
            base.extend(ledger_rows)

    # Full-document fallback for OCRs where the annual header and continuation rows
    # are split across pages. It is used only when it is demonstrably more complete
    # than page parsing (or page parsing returned nothing).
    candidates=[
        parse_body_lekarz_number_amount(case_pk,institution_pk,placowka,0,doc),
        parse_specialty_amount_lines(case_pk,institution_pk,placowka,0,doc),
        parse_explicit_annual_prose_salary(case_pk,institution_pk,placowka,0,doc),
    ]
    candidates=[_rank_dedup(_technical_filter(g)) for g in candidates if g]

    def amounts(rs):
        return [round((r.brutto if r.brutto is not None else r.netto or 0),2) for r in rs]
    def multiset_subset(a,b):
        from collections import Counter
        ca,cb=Counter(a),Counter(b)
        return all(cb[k]>=v for k,v in ca.items())

    best=base
    for cand in candidates:
        if not cand:
            continue
        if not best:
            best=cand
            continue
        # Replace an incomplete page-level extraction only when every amount already
        # extracted is represented in the fuller document-level candidate.
        if ledger_rows:
            # Once a monthly ledger has been annualized, document-level fallback
            # must not replace the combined result.
            continue
        if len(cand)>len(best) and multiset_subset(amounts(best),amounts(cand)):
            best=cand

    final_rows=filter_registry_capital_false_rows(_rank_dedup(best),doc)

    # Final record-level pass for tables whose columns are separate employment
    # forms. This also covers rows recovered by continuation parsers: the raw
    # row still preserves the original column order, so we can infer UoP/UZ
    # from non-zero cells without hardcoding an institution.
    if infer_contract_from_multi_columns is not None:
        header_lines=[]
        for line in doc.splitlines():
            if '|' not in line:
                continue
            cells=split_markdown_row(line)
            if len(cells)<3:
                continue
            cts=[detect_contract(c) for c in cells]
            if len({x for x in cts if x})>=2:
                header_lines.append([clean_header(x) for x in cells])
        for r in final_rows:
            raw_cells=[norm_space(x) for x in str(r.raw_row or '').split('|')]
            raw_cells=[x for x in raw_cells if x!='']
            for hs in header_lines:
                # Match by number of financial columns, allowing one leading
                # index/name column omitted by normalization.
                if len(raw_cells)!=len(hs):
                    continue
                inf=infer_contract_from_multi_columns(hs,raw_cells)
                if inf and len(inf['active_types'])==1:
                    r.typ_umowy=inf['contract_type']
                    break

    # Reconcile separate contract columns across page/OCR continuations.
    # Blank cells are significant: different contract columns may have different
    # numbers of populated rows. Never shift values left after an empty cell.
    if document_multi_contract_row_map is not None:
        mcmap=document_multi_contract_row_map(doc)
        if mcmap:
            def rawkey(s):
                return ' | '.join(norm_space(x) for x in str(s or '').strip().strip('|').split('|'))
            byraw={}
            for r in final_rows:
                byraw.setdefault(rawkey(r.raw_row),[]).append(r)
            additions=[]
            for rk, expected in mcmap.items():
                existing=byraw.get(rk,[])
                # If the parser already retained one total equal to the sum of
                # several active contract columns, keep that total as one record
                # and mark it mixed. Do not add component amounts on top of it.
                exp_sum=sum(float(a) for _,a in expected)
                total_match=None
                if len(expected)>1:
                    for er in existing:
                        ev=er.brutto if er.brutto is not None else er.netto
                        if ev is not None and abs(float(ev)-exp_sum)<0.02:
                            total_match=er
                            break
                if total_match is not None:
                    total_match.typ_umowy=' / '.join(dict.fromkeys(ct for ct,_ in expected))
                    continue
                for ct, amount in expected:
                    matched=None
                    for r in existing:
                        rv=r.brutto if r.brutto is not None else r.netto
                        if rv is not None and abs(float(rv)-float(amount))<0.02:
                            matched=r
                            break
                    if matched is not None:
                        matched.typ_umowy=ct
                        continue
                    # The generic parser may have skipped a populated column.
                    # Add only the missing amount from the same source row.
                    if existing:
                        proto=existing[0]
                        additions.append(SalaryRow(
                            proto.case_pk, proto.institution_pk, proto.placowka,
                            proto.nazwa, proto.specjalizacja, ct, None, amount,
                            proto.strona, 'markdown-multi-contract-reconcile',
                            'wysoka', proto.raw_row,
                            (proto.komentarz or '') + '; odzyskano brakującą niepustą kolumnę typu umowy'
                        ))
            final_rows.extend(additions)

    # Conservative semantic recovery from the record itself or its governing
    # section/list. Existing row-level values always win.
    if infer_contract_from_record_and_section is not None:
        for r in final_rows:
            if (r.typ_umowy or '').strip():
                continue
            inf=infer_contract_from_record_and_section(doc,r.raw_row)
            if inf:
                r.typ_umowy=inf[0]
                extra=f"typ umowy z semantyki rekordu/sekcji: {inf[1]}"
                r.komentarz=((r.komentarz or '').strip()+'; '+extra).strip('; ')

    # Recover missing contract type from the exact attachment/local section that
    # contains this row. Existing row-level contract values always win.
    if contract_zones is not None and match_row_to_zone is not None:
        zones=contract_zones(doc)
        if zones:
            for r in final_rows:
                if (r.typ_umowy or '').strip():
                    continue
                m=match_row_to_zone(
                    raw_row=r.raw_row,
                    name=r.nazwa,
                    gross=r.brutto,
                    net=r.netto,
                    zones=zones,
                )
                if not m:
                    continue
                r.typ_umowy=m['contract_type']
                extra=(
                    f"typ umowy z kontekstu załącznika: {m['filename']} "
                    f"({m['source']}; {m['evidence']}; match={m['match_reasons']})"
                )
                r.komentarz=((r.komentarz or '').strip()+'; '+extra).strip('; ')
    # Replace a weaker generic extraction with a structured section-list parse
    # when the source is clearly of the form:
    #   Oddział X:
    #   1. lekarz ... — kwota
    #   2. lekarz ... — kwota
    # This also repairs common OCR corruption inside amounts.
    if parse_section_salary_list is not None:
        sec_items=parse_section_salary_list(doc)
        if sec_items:
            old_amounts=[]
            for r in final_rows:
                v=r.brutto if r.brutto is not None else r.netto
                if v is not None:
                    old_amounts.append(round(float(v),2))
            from collections import Counter as _Counter
            oldc=_Counter(old_amounts)
            newc=_Counter(round(float(x.amount),2) for x in sec_items)
            overlap=sum((oldc & newc).values())
            # Conservative activation: the section parser must cover nearly all
            # existing rows and produce at least as many records.
            if len(sec_items)>=len(final_rows) and overlap>=max(10,int(0.85*len(final_rows))):
                # Reuse metadata from matching old rows where possible.
                pools={}
                for r in final_rows:
                    v=r.brutto if r.brutto is not None else r.netto
                    if v is None:
                        continue
                    pools.setdefault(round(float(v),2),[]).append(r)
                rebuilt=[]
                for x in sec_items:
                    old=None
                    pool=pools.get(round(float(x.amount),2),[])
                    if pool:
                        old=pool.pop(0)
                    rebuilt.append(SalaryRow(
                        case_pk,
                        institution_pk,
                        placowka,
                        f'Lekarz {x.index}',
                        '',
                        old.typ_umowy if old is not None else '',
                        None,
                        x.amount,
                        old.strona if old is not None else 0,
                        'section-salary-list',
                        'wysoka',
                        x.raw_row,
                        ((old.komentarz if old is not None else '') +
                         '; rekord z sekcyjnej listy wynagrodzeń').strip('; '),
                        x.unit,
                    ))
                final_rows=rebuilt

    # Separate organizational unit/ward from medical specialization.
    # Existing combined values such as "ODDZIAŁ ... — Lekarz specjalista"
    # are split; explicit unit cells and governing section headings are recovered.
    if infer_unit_and_specialization is not None:
        for r in final_rows:
            unit, spec = infer_unit_and_specialization(doc, r.raw_row, r.specjalizacja)
            if unit:
                r.jednostka_oddzial = unit
            r.specjalizacja = spec

    # Stronger organizational-unit recovery based on explicit table-column
    # semantics and stateful plain-text section headings. These rules may
    # override a weaker proximity-derived unit, because their provenance is
    # structurally tied to the exact source row.
    if document_unit_row_map is not None or section_unit_map is not None:
        def _unit_key(s):
            return ' | '.join(
                norm_space(x) for x in str(s or '').strip().strip('|').split('|')
            )
        colmap=document_unit_row_map(doc) if document_unit_row_map is not None else {}
        idxmap=document_unit_index_amount_map(doc) if document_unit_index_amount_map is not None else {}
        secmap=section_unit_map(doc) if section_unit_map is not None else {}
        secmap_norm={norm_space(k):v for k,v in secmap.items()}
        for r in final_rows:
            rk=_unit_key(r.raw_row)
            exact=colmap.get(rk)

            # More robust table provenance: match Lp + remuneration amount.
            # This survives OCR dropping empty trailing cells.
            idx_exact=None
            m_idx=re.match(r'^\s*(\d+)\b', str(r.raw_row or ''))
            if not m_idx:
                m_idx=re.fullmatch(r'(?i)Lekarz\s+(\d+)', norm_space(r.nazwa))
            rv=r.brutto if r.brutto is not None else r.netto
            if m_idx and rv is not None:
                idx_exact=idxmap.get((int(m_idx.group(1)), int(round(float(rv)*100))))

            if idx_exact:
                r.jednostka_oddzial=idx_exact
            elif exact:
                r.jednostka_oddzial=exact
            else:
                sr=norm_space(r.raw_row)
                sec=secmap_norm.get(sr)
                if sec:
                    r.jednostka_oddzial=sec
                elif inline_ocr_section_unit is not None:
                    inline=inline_ocr_section_unit(r.raw_row)
                    if inline:
                        r.jednostka_oddzial=inline

            if (
                not (r.jednostka_oddzial or '').strip()
                and shifted_row_unit_candidate is not None
            ):
                shifted=shifted_row_unit_candidate(r.raw_row)
                if shifted:
                    r.jednostka_oddzial=shifted

            # A former generic table parser sometimes copied the unit-column
            # value into `specjalizacja`. Once structural unit provenance is
            # known, remove only an exact duplicate; never infer/erase a
            # genuinely different medical specialization.
            if (
                (r.jednostka_oddzial or '').strip()
                and (r.specjalizacja or '').strip()
                and norm_space(r.jednostka_oddzial).casefold()
                    == norm_space(r.specjalizacja).casefold()
            ):
                r.specjalizacja=''

    # Recover missing medical specialization from the record itself.
    if infer_specialization_from_raw_row is not None:
        for r in final_rows:
            inf=infer_specialization_from_raw_row(
                r.raw_row, r.specjalizacja, r.jednostka_oddzial
            )
            if inf:
                r.specjalizacja=inf[0]
                extra=inf[1]
                r.komentarz=((r.komentarz or '').strip()+'; '+extra).strip('; ')

    # Dedicated physician-name field. Prefer explicit table semantics, then
    # conservative structured-row inference. Move exact historical false
    # positives out of `specjalizacja`.
    if document_person_name_maps is not None or infer_person_name is not None:
        raw_name_map, idx_name_map = document_person_name_maps(doc) if document_person_name_maps is not None else ({}, {})
        for r in final_rows:
            key=' | '.join(norm_space(x) for x in str(r.raw_row or '').strip().strip('|').split('|'))
            person=raw_name_map.get(key,'')
            rv=r.brutto if r.brutto is not None else r.netto
            m_idx=re.match(r'^\s*(\d+)\b', str(r.raw_row or ''))
            if not person and m_idx and rv is not None:
                person=idx_name_map.get((int(m_idx.group(1)), int(round(float(rv)*100))), '')
            if not person and infer_person_name is not None:
                person=infer_person_name(r.raw_row, r.specjalizacja, r.jednostka_oddzial)
            if person:
                r.imie_nazwisko=person
                if (r.specjalizacja or '').strip() and norm_space(r.specjalizacja).casefold()==norm_space(person).casefold():
                    r.specjalizacja=''

    if extract_status is not None:
        for r in final_rows:
            status, clear_spec = extract_status(r.nazwa, r.raw_row, r.specjalizacja)
            if status:
                r.stanowisko_status = status
            if clear_spec:
                r.specjalizacja = ''

    # Recover anonymised initials / physician identifiers into a dedicated
    # field, separate from full person names.
    if document_initial_maps is not None or infer_initials_from_row is not None:
        imap=document_initial_maps(doc) if document_initial_maps is not None else {}
        for r in final_rows:
            key=' | '.join(norm_space(x) for x in str(r.raw_row or '').strip().strip('|').split('|'))
            ini=imap.get(key,'')
            if not ini and infer_initials_from_row is not None:
                ini=infer_initials_from_row(r.raw_row)
            if ini:
                r.inicjaly=ini

    return validate_case_rows(final_rows)

def _store_case_status(con, rows):
    """Parse or process the `_store_case_status` layout/stage."""
    con.execute('DROP TABLE IF EXISTS salaries_case_status')
    con.execute("""
        CREATE TABLE salaries_case_status (
            case_pk INTEGER, institution_pk INTEGER, placówka TEXT,
            status TEXT, reason TEXT, parsed_candidate_rows INTEGER
        )
    
""")
    con.executemany("""
        INSERT INTO salaries_case_status
        (case_pk, institution_pk, placówka, status, reason, parsed_candidate_rows)
        VALUES (?, ?, ?, ?, ?, ?)
    
""", rows)
    con.commit()



