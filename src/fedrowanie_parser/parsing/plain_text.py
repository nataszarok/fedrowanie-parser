"""Plain-text and section-state fallback parsers."""
from __future__ import annotations

import re
from typing import Optional
from ..models import SalaryRow
from ..constants import SPECIALIZATION_WORDS
from ..processing.normalization import (
    norm_space,
    parse_money,
    money_cells,
    money_values,
    is_metadata_or_date,
    mentions_other_year,
    is_summary_row,
    detect_contract,
    amount_kind,
    clean_header,
    split_markdown_row,
    split_md_row,
    is_separator_row,
    header_has_money_context,
    infer_name_and_spec,
    parse_idx,
    label_for_row,
    table_should_be_excluded,
    semantic_annual_salary_columns,
)
from .layouts import page_context_contract

__all__ = [
    "parse_plain_lines",
    "parse_section_state_rows",
]


def parse_plain_lines(
    case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str
) -> list[SalaryRow]:
    """Parse salary records from unstructured plain-text lines."""
    out: list[SalaryRow] = []
    lines = [norm_space(x) for x in page.splitlines()]
    page_kind = amount_kind(page[:1200])
    page_contract = detect_contract(page[:1200])
    inline = re.compile(
        "^(?:\\|\\s*)?(?P<idx>\\d{1,4})[.)]?\\s+(?P<label>.*?)(?:\\s*[—–-]\\s*|\\s{2,})(?P<amount>(?:\\d{1,3}(?:[ .]\\d{3})+|\\d{4,12})(?:[,.]\\d{1,2})?\\s*(?:zł|PLN)?)\\s*\\|?$",
        re.I,
    )
    idx_amount = re.compile(
        "^(?P<idx>\\d{1,4})[.)]*\\s+(?P<amount>\\d{1,3}(?:[ .]\\d{3})+(?:[,.]\\d{1,2})?|\\d{4,7}(?:[,.]\\d{1,2})?)\\s*(?:zł)?$",
        re.I,
    )

    def near_summary_marker(pos: int, radius: int = 10) -> bool:
        lo = max(0, pos - radius)
        hi = min(len(lines), pos + radius + 1)
        ctx = " ".join(lines[lo:hi])
        return bool(
            re.search("(?i)\\b(?:razem|ogółem|ogolem|suma|łącznie|lacznie)\\s*:?", ctx)
        )

    consumed = set()
    for n, line in enumerate(lines):
        if not line or "|" in line:
            continue
        if (
            is_metadata_or_date(line)
            or mentions_other_year(line)
            or is_summary_row(line)
        ):
            continue
        m = inline.match(line)
        if m:
            label_probe = norm_space(m.group("label"))
            if (
                not label_probe or re.fullmatch("\\d*", label_probe)
            ) and near_summary_marker(n):
                continue
            val = parse_money(m.group("amount"))
            if val is None:
                continue
            idx = int(m.group("idx"))
            label = norm_space(m.group("label"))
            contract = page_context_contract(lines, n, page_contract)
            spec = label if SPECIALIZATION_WORDS.search(label) else ""
            name = (
                label
                if re.search("(?i)^lekarz\\s*(?:nr|n)?\\s*\\d+|inicja", label)
                else f"Lekarz {idx}"
            )
            kind = (
                amount_kind("\n".join(lines[max(0, n - 8) : n + 1]))
                if page_kind == "brutto"
                else page_kind
            )
            out.append(
                SalaryRow(
                    case_pk,
                    institution_pk,
                    placowka,
                    name,
                    spec,
                    contract,
                    val if kind == "netto" else None,
                    val if kind == "brutto" else None,
                    page_no,
                    "plain-inline",
                    "średnia",
                    line,
                )
            )
            consumed.add(n)
            continue
        m = idx_amount.match(line)
        if m:
            if near_summary_marker(n):
                continue
            val = parse_money(m.group("amount"))
            idx = int(m.group("idx"))
            if val is None:
                continue
            contract = page_context_contract(lines, n, page_contract)
            kind = page_kind
            out.append(
                SalaryRow(
                    case_pk,
                    institution_pk,
                    placowka,
                    f"Lekarz {idx}",
                    "",
                    contract,
                    val if kind == "netto" else None,
                    val if kind == "brutto" else None,
                    page_no,
                    "plain-index-amount",
                    "średnia",
                    line,
                )
            )
            consumed.add(n)
    for n in range(len(lines) - 2):
        if n in consumed:
            continue
        if not re.fullmatch("\\d{1,4}", lines[n] or ""):
            continue
        idx = int(lines[n])
        window = lines[n + 1 : n + 5]
        if any((is_summary_row(x) or is_metadata_or_date(x) for x in window)):
            continue
        amount_pos = None
        val = None
        for j, x in enumerate(window, 1):
            ms = money_cells(x)
            if len(ms) == 1 and re.fullmatch(
                "\\d{1,3}(?:[ .]\\d{3})*(?:[,.]\\d{1,2})?\\s*(?:zł)?", x, re.I
            ):
                amount_pos = n + j
                val = ms[0][1]
                break
        if val is None:
            continue
        middle = " ".join(lines[n + 1 : amount_pos])
        if mentions_other_year(middle) or is_summary_row(middle):
            continue
        spec = middle if SPECIALIZATION_WORDS.search(middle) else ""
        contract = detect_contract(
            middle, page_context_contract(lines, n, page_contract)
        )
        kind = amount_kind("\n".join(lines[max(0, n - 12) : amount_pos + 1]))
        out.append(
            SalaryRow(
                case_pk,
                institution_pk,
                placowka,
                f"Lekarz {idx}",
                spec,
                contract,
                val if kind == "netto" else None,
                val if kind == "brutto" else None,
                page_no,
                "plain-vertical",
                "średnia",
                " | ".join(lines[n : amount_pos + 1]),
            )
        )
    return out


def parse_section_state_rows(
    case_pk: int, institution_pk: Optional[int], placowka: str, doc: str
) -> list[SalaryRow]:
    """Parse rows that inherit semantic context from section headings."""
    out: list[SalaryRow] = []
    current_contract = ""
    current_page: Optional[int] = None
    in_salary_section = False
    page_start = re.compile("(?i)-+\\s*początek strony\\s+(\\d+)\\s*-+")
    sectionish = re.compile(
        "(?i)(?:umow[ayę]\\s+o\\s+prac|umow[ayę]\\s+zlecen|zlecenie|kontrakt|cywilno[- ]?prawn)"
    )
    doctor_label = re.compile("(?i)^lekarz\\s+(\\d{1,4})$")
    for raw in (doc or "").splitlines():
        pm = page_start.search(raw)
        if pm:
            current_page = int(pm.group(1))
            continue
        line = norm_space(raw)
        if not line:
            continue
        if "|" not in raw and sectionish.search(line):
            current_contract = detect_contract(line, current_contract)
            in_salary_section = bool(current_contract)
            continue
        cells = split_markdown_row(raw)
        if len(cells) < 2:
            continue
        joined = " ".join(cells)
        if sectionish.search(joined) and (not money_cells(joined)):
            current_contract = detect_contract(joined, current_contract)
            in_salary_section = bool(current_contract)
            continue
        if not in_salary_section or not current_contract:
            continue
        if (
            is_separator_row(cells)
            or is_summary_row(line)
            or is_metadata_or_date(line)
            or mentions_other_year(line)
        ):
            continue
        if len(cells) == 2:
            m = doctor_label.fullmatch(cells[0])
            vals = money_cells(cells[1])
            if m and len(vals) == 1:
                val = vals[0][1]
                out.append(
                    SalaryRow(
                        case_pk,
                        institution_pk,
                        placowka,
                        f"Lekarz {int(m.group(1))}",
                        "",
                        current_contract,
                        None,
                        val,
                        current_page,
                        "markdown-section-state",
                        "wysoka",
                        line,
                    )
                )
                continue
        if len(cells) == 3:
            c0, c1, c2 = cells
            vals = money_cells(c2)
            headerish = (
                bool(re.fullmatch("(?i)nazwisko", c0))
                or bool(re.fullmatch("(?i)imi[ęe]", c1))
                or bool(re.search("(?i)^wynagrod", c2))
            )
            text_identity = bool(
                c0 and c1 and (not money_cells(c0)) and (not money_cells(c1))
            )
            if len(vals) == 1 and text_identity and (not headerish):
                val = vals[0][1]
                name = norm_space(f"{c0} {c1}")
                out.append(
                    SalaryRow(
                        case_pk,
                        institution_pk,
                        placowka,
                        name,
                        "",
                        current_contract,
                        None,
                        val,
                        current_page,
                        "markdown-section-state",
                        "wysoka",
                        line,
                    )
                )
    return out
