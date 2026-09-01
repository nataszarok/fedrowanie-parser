"""Extraction orchestration and semantic enrichment."""
from __future__ import annotations
from dataclasses import replace
import re
from .models import CaseParseStatus, ExtractionResult, SalaryRow, SourceCase
from .constants import (
    GROSS_RE,
    NET_RE,
    PARSER_RANK,
    STRUCTURED_METADATA_PARSERS,
    YEAR,
)
from .services.case_extraction import validate_case_rows


__all__ = [
    "extract_cases",
]

# Public package APIs are intentionally imported wholesale; each module defines __all__.
from .processing.api import *
from .processing.case_flags import classify_case_flags
from .parsing.tables import *
from .parsing.layouts import *
from .parsing.plain_text import *
from .enrichment.api import *
from .special_cases.api import *

def extract_cases(cases: list[SourceCase]) -> ExtractionResult:
    """Extract normalized salary rows and case-level statuses from source cases."""
    accepted: list[SalaryRow] = []
    statuses: list[CaseParseStatus] = []

    for case in cases:
        doc, meta = recipient_document(case.text)
        flags = classify_case_flags(
            doc,
            has_unprocessed_attachment=bool(case.unprocessed_attachments),
        )

        if not meta["thread_detected"]:
            statuses.append(
                CaseParseStatus(
                    case_pk=case.case_pk,
                    institution_pk=case.institution_pk,
                    institution_name=case.institution_name,
                    status="NO_SUBSTANTIVE_DATA_DETECTED",
                    reason="recipient_thread_not_detected",
                    parsed_candidate_rows=0,
                    flags=flags,
                )
            )
            continue

        if meta["substantive_recipient_messages"] == 0:
            statuses.append(
                CaseParseStatus(
                    case_pk=case.case_pk,
                    institution_pk=case.institution_pk,
                    institution_name=case.institution_name,
                    status="NO_SUBSTANTIVE_DATA_DETECTED",
                    reason="no_substantive_recipient_reply",
                    parsed_candidate_rows=0,
                    flags=flags,
                )
            )
            continue

        rows = _case_rows(
            case.case_pk,
            case.institution_pk,
            case.institution_name,
            doc,
        )

        comment = topn_comment(doc)
        if comment:
            for row in rows:
                row.comment = comment

        status, reason = correspondence_status(doc, rows)
        flags = replace(
            flags,
            refusal_detected=(
                "REFUSAL" in status
                or "refusal" in (reason or "").lower()
            ),
        )
        if status.startswith("INDIVIDUAL_ANNUAL_2025"):
            accepted.extend(rows)

        statuses.append(
            CaseParseStatus(
                case_pk=case.case_pk,
                institution_pk=case.institution_pk,
                institution_name=case.institution_name,
                status=status,
                reason=reason,
                parsed_candidate_rows=len(rows),
                flags=flags,
            )
        )

    return ExtractionResult(rows=accepted, statuses=statuses)


def _page_rows(case_pk, institution_pk, institution_name, page_no, page, doc, inherited_contract, inherited_kind, inherited_spec):
    """Run the parser families applicable to one document page."""
    vals = money_values(page)
    if (vals and max(vals) < 1000
            and not re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', page)):
        return []
    if page_is_group_aggregate_salary_table(page):
        return []
    args = (case_pk, institution_pk, institution_name, page_no, page)
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
    vertical_index_amounts = parse_vertical_index_amount_series(*args)
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
    vertical_named = [r for r in vertical_named if not re.fullmatch('[\\d\\s.,]+\\s*zł', r.source_name or '', re.I)]
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
    strong = named_inline or lekarz_inline or vertical_struct or gross_net_struct or parallel_idx or anon_inline or bracket_rows or embedded_list or amount_series or vertical_index_amounts or specialty_lines or role_named or named_table or two_section or annual_prose or body_lekarz or body_lp or parallel_lists or anon_amounts or annual_contract_lines or contract_practice_costs or forma_rows or single_anon_annual or named_colon_annual
    if named_table or two_section or annual_prose:
        plain = [r for r in plain if r.parser not in ('plain-inline', 'plain-index-amount', 'plain-vertical', 'plain-named')]
        vertical_pairs = []
    if strong:
        plain = [r for r in plain if r.parser not in ('plain-inline', 'plain-index-amount', 'plain-vertical')]
    groups = (md, md_cont, named_inline, lekarz_inline, vertical_struct, gross_net_struct, parallel_idx, anon_inline, indexed_single, total_gross_cont, bracket_rows, embedded_list, amount_series, vertical_index_amounts, specialty_lines, role_named, named_table, two_section, annual_prose, body_lekarz, body_lp, parallel_lists, anon_amounts, annual_contract_lines, contract_practice_costs, forma_rows, single_anon_annual, named_colon_annual, vertical_pairs, vertical_named, ocr_contract, plain)
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
        if r.parser == 'markdown-table' and (r.gross_compensation or r.net_compensation or 0) < 1000 and re.search('(?i)okres:|od 01 do 12', r.raw_row):
            continue
        out.append(r)
    return out

def _rank_dedup(rows):
    """Parse or process the `_rank_dedup` layout/stage."""
    raw_best = {}
    for r in rows:
        raw = norm_space(r.raw_row).lower()
        indexed = bool(re.match('^\\|?\\s*\\d{1,4}\\s*[.):]?\\s*\\|', raw))
        key = (r.case_pk, None if indexed else r.page_number, raw, r.net_compensation, r.gross_compensation)
        old = raw_best.get(key)
        if (
            old is None
            or ((r.contract_type or '').strip() and not (old.contract_type or '').strip())
            or (
                bool((r.contract_type or '').strip()) == bool((old.contract_type or '').strip())
                and PARSER_RANK.get(r.parser, 0) > PARSER_RANK.get(old.parser, 0)
            )
        ):
            raw_best[key] = r
    best = {}
    for r in raw_best.values():
        raw = norm_space(r.raw_row).lower()
        if re.match('^\\|?\\s*\\d{1,4}\\s*[.):]?\\s*\\|', raw):
            key = (r.case_pk, r.page_number, raw, r.net_compensation, r.gross_compensation)
        else:
            key = (r.case_pk, r.page_number, norm_space(r.source_name).lower(), norm_space(r.specialization).lower(), norm_space(r.contract_type).lower(), r.net_compensation, r.gross_compensation)
        old = best.get(key)
        if old is None or PARSER_RANK.get(r.parser, 0) > PARSER_RANK.get(old.parser, 0):
            best[key] = r
    return list(best.values())


def _reconcile_numbered_annual_series(
    base_rows: list[SalaryRow],
    segment_rows: list[SalaryRow],
) -> list[SalaryRow]:
    """Merge a structured numbered segment with rows parsed from other layouts."""
    if not segment_rows:
        return base_rows

    def index_of(row: SalaryRow) -> int | None:
        match = re.fullmatch(r"(?i)Lekarz\s+(\d{1,4})", norm_space(row.source_name))
        return int(match.group(1)) if match else None

    segment_by_index = {
        idx: row
        for row in segment_rows
        if (idx := index_of(row)) is not None
    }
    if not segment_by_index:
        return base_rows

    start = min(segment_by_index)
    end = max(segment_by_index)
    if set(segment_by_index) != set(range(start, end + 1)):
        return base_rows

    base_by_index: dict[int, list[SalaryRow]] = {}
    non_indexed: list[SalaryRow] = []
    for row in base_rows:
        idx = index_of(row)
        if idx is None:
            non_indexed.append(row)
        else:
            base_by_index.setdefault(idx, []).append(row)

    # Reconciliation is activated only when the structured segment plus existing
    # rows forms a complete logical sequence from 1 through the segment end.
    available = set(base_by_index) | set(segment_by_index)
    if not set(range(1, end + 1)).issubset(available):
        return base_rows

    merged: list[SalaryRow] = list(non_indexed)
    for idx in range(1, end + 1):
        if idx in segment_by_index:
            merged.append(segment_by_index[idx])
            continue

        # Rows before a layout switch remain owned by the parser that recovered
        # them. Keep the highest-ranked candidate if more than one exists.
        candidates = base_by_index.get(idx, [])
        if candidates:
            merged.append(
                max(candidates, key=lambda row: PARSER_RANK.get(row.parser, 0))
            )

    # Preserve unrelated numbered records after the reconciled sequence, except
    # obvious year-as-index metadata false positives such as "Lekarz 2025 = 1".
    for idx, candidates in base_by_index.items():
        if idx <= end:
            continue
        for row in candidates:
            value = (
                row.gross_compensation
                if row.gross_compensation is not None
                else row.net_compensation
            )
            if idx == YEAR and value is not None and value < 1000:
                continue
            merged.append(row)

    return _rank_dedup(merged)

def _case_rows(case_pk, institution_pk, institution_name, doc):
    """Extract, reconcile and enrich salary rows for a single case."""
    if aggregate_count_total_guard(doc):
        return []
    parallel = parse_parallel_name_amount_lists(case_pk, institution_pk, institution_name, doc)
    if parallel:
        return filter_registry_capital_false_rows(_rank_dedup(_technical_filter(parallel)), doc)

    # A logical numbered annual-salary list may change layout between pages.
    # Parse the full document only as an additional structured segment; never
    # let it replace unrelated rows recovered by page/section parsers.
    vertical_document_rows = parse_vertical_index_amount_series(
        case_pk, institution_pk, institution_name, 0, doc
    )

    rows = parse_section_state_rows(case_pk, institution_pk, institution_name, doc)
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
        rows.extend(_page_rows(case_pk,institution_pk,institution_name,page_no,page,doc,contract,kind,spec))

    base=_rank_dedup(_technical_filter(rows))
    if vertical_document_rows:
        base=_reconcile_numbered_annual_series(base, vertical_document_rows)

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
                    case_pk,institution_pk,institution_name,a.display_name,'','',
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
        parse_body_lekarz_number_amount(case_pk,institution_pk,institution_name,0,doc),
        parse_specialty_amount_lines(case_pk,institution_pk,institution_name,0,doc),
        parse_explicit_annual_prose_salary(case_pk,institution_pk,institution_name,0,doc),
    ]
    candidates=[_rank_dedup(_technical_filter(g)) for g in candidates if g]

    def amounts(rs):
        return [round((r.gross_compensation if r.gross_compensation is not None else r.net_compensation or 0),2) for r in rs]
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
                    r.contract_type=inf['contract_type']
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
                        ev=er.gross_compensation if er.gross_compensation is not None else er.net_compensation
                        if ev is not None and abs(float(ev)-exp_sum)<0.02:
                            total_match=er
                            break
                if total_match is not None:
                    total_match.contract_type=' / '.join(dict.fromkeys(ct for ct,_ in expected))
                    continue
                for ct, amount in expected:
                    matched=None
                    for r in existing:
                        rv=r.gross_compensation if r.gross_compensation is not None else r.net_compensation
                        if rv is not None and abs(float(rv)-float(amount))<0.02:
                            matched=r
                            break
                    if matched is not None:
                        matched.contract_type=ct
                        continue
                    # The generic parser may have skipped a populated column.
                    # Add only the missing amount from the same source row.
                    if existing:
                        proto=existing[0]
                        additions.append(SalaryRow(
                            proto.case_pk, proto.institution_pk, proto.institution_name,
                            proto.source_name, proto.specialization, ct, None, amount,
                            proto.page_number, 'markdown-multi-contract-reconcile',
                            'wysoka', proto.raw_row,
                            (proto.comment or '') + '; odzyskano brakującą niepustą kolumnę typu umowy'
                        ))
            final_rows.extend(additions)

    # Conservative semantic recovery from the record itself or its governing
    # section/list. Existing row-level values always win.
    if infer_contract_from_record_and_section is not None:
        for r in final_rows:
            if (r.contract_type or '').strip():
                continue
            inf=infer_contract_from_record_and_section(doc,r.raw_row)
            if inf:
                r.contract_type=inf[0]
                extra=f"typ umowy z semantyki rekordu/sekcji: {inf[1]}"
                r.comment=((r.comment or '').strip()+'; '+extra).strip('; ')

    # Recover missing contract type from the exact attachment/local section that
    # contains this row. Existing row-level contract values always win.
    if contract_zones is not None and match_row_to_zone is not None:
        zones=contract_zones(doc)
        if zones:
            for r in final_rows:
                if (r.contract_type or '').strip():
                    continue
                m=match_row_to_zone(
                    raw_row=r.raw_row,
                    name=r.source_name,
                    gross=r.gross_compensation,
                    net=r.net_compensation,
                    zones=zones,
                )
                if not m:
                    continue
                r.contract_type=m['contract_type']
                extra=(
                    f"typ umowy z kontekstu załącznika: {m['filename']} "
                    f"({m['source']}; {m['evidence']}; match={m['match_reasons']})"
                )
                r.comment=((r.comment or '').strip()+'; '+extra).strip('; ')
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
                v=r.gross_compensation if r.gross_compensation is not None else r.net_compensation
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
                    v=r.gross_compensation if r.gross_compensation is not None else r.net_compensation
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
                        institution_name,
                        f'Lekarz {x.index}',
                        '',
                        old.contract_type if old is not None else '',
                        None,
                        x.amount,
                        old.page_number if old is not None else 0,
                        'section-salary-list',
                        'wysoka',
                        x.raw_row,
                        ((old.comment if old is not None else '') +
                         '; rekord z sekcyjnej listy wynagrodzeń').strip('; '),
                        x.unit,
                    ))
                final_rows=rebuilt

    # Separate organizational unit/ward from medical specialization.
    # Existing combined values such as "ODDZIAŁ ... — Lekarz specjalista"
    # are split; explicit unit cells and governing section headings are recovered.
    if infer_unit_and_specialization is not None:
        for r in final_rows:
            unit, spec = infer_unit_and_specialization(doc, r.raw_row, r.specialization)
            if unit:
                r.organizational_unit = unit
            r.specialization = spec

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
                m_idx=re.fullmatch(r'(?i)Lekarz\s+(\d+)', norm_space(r.source_name))
            rv=r.gross_compensation if r.gross_compensation is not None else r.net_compensation
            if m_idx and rv is not None:
                idx_exact=idxmap.get((int(m_idx.group(1)), int(round(float(rv)*100))))

            if idx_exact:
                r.organizational_unit=idx_exact
            elif exact:
                r.organizational_unit=exact
            else:
                sr=norm_space(r.raw_row)
                sec=secmap_norm.get(sr)
                if sec:
                    r.organizational_unit=sec
                elif inline_ocr_section_unit is not None:
                    inline=inline_ocr_section_unit(r.raw_row)
                    if inline:
                        r.organizational_unit=inline

            if (
                not (r.organizational_unit or '').strip()
                and shifted_row_unit_candidate is not None
            ):
                shifted=shifted_row_unit_candidate(r.raw_row)
                if shifted:
                    r.organizational_unit=shifted

            # A former generic table parser sometimes copied the unit-column
            # value into `specialization`. Once structural unit provenance is
            # known, remove only an exact duplicate; never infer/erase a
            # genuinely different medical specialization.
            if (
                (r.organizational_unit or '').strip()
                and (r.specialization or '').strip()
                and norm_space(r.organizational_unit).casefold()
                    == norm_space(r.specialization).casefold()
            ):
                r.specialization=''

    # Recover missing medical specialization from the record itself.
    if infer_specialization_from_raw_row is not None:
        for r in final_rows:
            inf=infer_specialization_from_raw_row(
                r.raw_row, r.specialization, r.organizational_unit
            )
            if inf:
                r.specialization=inf[0]
                extra=inf[1]
                r.comment=((r.comment or '').strip()+'; '+extra).strip('; ')

    # Dedicated physician-name field. Prefer explicit table semantics, then
    # conservative structured-row inference. Move exact historical false
    # positives out of `specialization`.
    if document_person_name_maps is not None or infer_person_name is not None:
        raw_name_map, idx_name_map = document_person_name_maps(doc) if document_person_name_maps is not None else ({}, {})
        for r in final_rows:
            key=' | '.join(norm_space(x) for x in str(r.raw_row or '').strip().strip('|').split('|'))
            person=raw_name_map.get(key,'')
            rv=r.gross_compensation if r.gross_compensation is not None else r.net_compensation
            m_idx=re.match(r'^\s*(\d+)\b', str(r.raw_row or ''))
            if not person and m_idx and rv is not None:
                person=idx_name_map.get((int(m_idx.group(1)), int(round(float(rv)*100))), '')
            if not person and infer_person_name is not None:
                person=infer_person_name(r.raw_row, r.specialization, r.organizational_unit)
            if person:
                r.doctor_name=person
                if (r.specialization or '').strip() and norm_space(r.specialization).casefold()==norm_space(person).casefold():
                    r.specialization=''

    if extract_status is not None:
        for r in final_rows:
            status, clear_spec = extract_status(r.source_name, r.raw_row, r.specialization)
            if status:
                r.doctor_status = status
            if clear_spec:
                r.specialization = ''

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
                r.doctor_initials=ini

    final_rows = classify_salary_recipients(final_rows, doc)
    return validate_case_rows(final_rows)
