"""Interpret tables that encode contract types in separate salary columns."""


from __future__ import annotations

from ..constants import (
    MULTI_CONTRACT_MONEY_RE,
)
import re
from typing import Optional


__all__ = [
    "contract_type_from_header",
    "contract_amount_columns",
    "infer_contract_from_multi_columns",
    "split_multi_contract_amounts",
    "expand_stacked_contract_headers",
    "document_multi_contract_row_map",
]


def contract_type_from_header(header: str) -> Optional[str]:
    """Infer the contract type encoded by a table-column header."""
    h = _norm(header).casefold()
    if re.search(r"um[oó]w\w*\s+o\s+prac[ęe]|\buop\b", h):
        return "umowa o pracę"
    if re.search(r"um[oó]w\w*\s+zlecen|\bzlecen", h):
        return "umowa zlecenia"
    if re.search(r"kontrakt|b2b|cywiln\w*[- ]?prawn", h):
        return "kontrakt/cywilnoprawna"
    return None


def contract_amount_columns(headers: list[str]) -> list[tuple[int, str]]:
    """Return salary columns whose headers encode a specific contract type."""
    out = []
    for i, h in enumerate(headers):
        ct = contract_type_from_header(h)
        if ct and re.search(
            r"(?i)brutto|wynagrodzen|kwot|umow|kontrakt|zlecen", h or ""
        ):
            out.append((i, ct))
    return out


def infer_contract_from_multi_columns(headers: list[str], cells: list[str]):
    """
    For a table with separate amount columns by contract type, infer the type(s)
    whose cell is non-zero. Returns None if fewer than two contract columns exist
    or if the row cannot be resolved safely.
    """
    cols = contract_amount_columns(headers)
    if len({ct for _, ct in cols}) < 2:
        return None
    active = []
    amounts = {}
    for i, ct in cols:
        if i >= len(cells):
            continue
        vals = _money(cells[i])
        if not vals:
            continue
        val = vals[-1]
        amounts[ct] = val
        if abs(val) > 0.004:
            active.append(ct)
    active = list(dict.fromkeys(active))
    if not active:
        return None
    if len(active) == 1:
        return {"contract_type": active[0], "active_types": active, "amounts": amounts}
    return {
        "contract_type": " / ".join(active),
        "active_types": active,
        "amounts": amounts,
    }


def split_multi_contract_amounts(headers: list[str], cells: list[str]):
    """
    Emit one (contract_type, amount) per non-zero contract-specific amount column.
    Useful when no 'total' column exists and the parser should retain each payment
    stream separately rather than silently selecting one column.
    """
    cols = contract_amount_columns(headers)
    if len({ct for _, ct in cols}) < 2:
        return []
    out = []
    for i, ct in cols:
        if i >= len(cells):
            continue
        vals = _money(cells[i])
        if not vals:
            continue
        val = vals[-1]
        if abs(val) > 0.004:
            out.append((ct, val))
    return out


def expand_stacked_contract_headers(headers: list[str], first_data_cells: list[str]):
    """
    Handle OCR/markdown tables where contract labels occupy the first row and
    'wynagrodzenie brutto' is the next row, which the generic parser otherwise
    mistakes for the first data row. Returns effective headers and whether the
    first_data_cells were consumed as a header continuation.
    """
    cts = [contract_type_from_header(h) for h in headers]
    if len({x for x in cts if x}) < 2:
        return headers, False
    if len(first_data_cells) != len(headers):
        return headers, False
    nonempty = [_norm(x) for x in first_data_cells if _norm(x)]
    if not nonempty:
        return headers, False
    if not all(re.search(r"(?i)wynagrodzen|brutto|netto|kwot", x) for x in nonempty):
        return headers, False
    eff = []
    for h, c in zip(headers, first_data_cells):
        eff.append(_norm((h or "") + " " + (c or "")))
    return eff, True


def document_multi_contract_row_map(doc: str):
    """
    Detect a markdown table whose columns are separate contract forms and return
    raw-row -> [(contract_type, amount), ...]. Blank cells are preserved.
    The last recognized multi-contract header remains active across OCR/page
    breaks while subsequent rows keep the same column count.
    """
    out = {}
    headers = None
    contract_cols = None
    for line in str(doc or "").splitlines():
        cells = _split_preserve(line)
        if not cells:
            continue

        # New contract header.
        cts = [contract_type_from_header(c) for c in cells]
        if len({x for x in cts if x}) >= 2:
            headers = cells
            contract_cols = [(i, ct) for i, ct in enumerate(cts) if ct]
            continue

        if headers is None or not contract_cols:
            continue
        if len(cells) != len(headers):
            continue
        if all(re.fullmatch(r":?-{3,}:?", c or "") or not c for c in cells):
            continue
        # Ignore second header row such as "wynagrodzenie brutto".
        if not any(_money(c) for c in cells):
            continue

        active = []
        for i, ct in contract_cols:
            if i >= len(cells):
                continue
            vals = _money(cells[i])
            if vals and abs(vals[-1]) > 0.004:
                active.append((ct, vals[-1]))
        if active:
            raw = " | ".join(cells)
            out[raw] = active
    return out


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip()


def _money(s):
    vals = []
    for m in MULTI_CONTRACT_MONEY_RE.finditer(str(s or "")):
        t = m.group(0).replace(" ", "").replace(".", "").replace(",", ".")
        try:
            vals.append(float(t))
        except ValueError:
            pass
    return vals


def _split_preserve(line: str):
    s = str(line or "").strip()
    if not s.startswith("|"):
        return []
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [_norm(x) for x in s.split("|")]
