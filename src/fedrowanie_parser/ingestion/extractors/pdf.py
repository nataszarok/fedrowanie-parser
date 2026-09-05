"""PDF extraction with geometry first and OCR only for image-only pages."""
from __future__ import annotations

import csv
import io
import re
import subprocess
import tempfile
from pathlib import Path

import pymupdf as fitz

from ..models import CellTable
from ..runtime import find_tesseract, tesseract_language

__all__ = ["extract_pdf"]

_money_pattern = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:[ .]\d{3})+|\d+)[,.]\d{2}(?!\d)"
)
_salary_context_pattern = re.compile(
    r"(?i)(?:wynagrodz|zarobk|warto(?:ść|sc)\s+faktur|wypłac|wyplac).{0,100}2025|"
    r"2025.{0,100}(?:wynagrodz|zarobk|warto(?:ść|sc)\s+faktur|wypłac|wyplac)"
)
_ocr_table_context_pattern = re.compile(
    r"(?is)(?:\blp\.?\b.{0,120}\bnazwa\b|funkcja\s+publiczna.{0,120}nazwisko|"
    r"pozostali\s+lekarze.{0,120}wynagrodz|łączna\s+wartość\s+faktur|laczna\s+wartosc\s+faktur|"
    r"zatrudnienie\s+na\s+podstawie\s+umowy\s+o\s+prac)"
)


def extract_pdf(path: Path) -> list[CellTable]:
    """Extract cell tables or OCR-derived salary rows from a PDF."""
    doc = fitz.open(path)
    out: list[CellTable] = []
    salary_context_active = False
    structured_table_active = False
    for page_number, page in enumerate(doc, 1):
        geometry_tables = _geometry_tables(path, page, page_number)
        if geometry_tables:
            out.extend(geometry_tables)
            continue

        text = page.get_text("text") or ""
        if len(text.strip()) >= 40:
            lines = _normalized_lines(text)
            if lines:
                out.append(CellTable(path, "text-lines", page_number, [[line] for line in lines], "pymupdf-text"))
            continue

        tesseract = find_tesseract()
        if not tesseract:
            raise RuntimeError(
                "PDF contains an image-only page and requires Tesseract OCR; "
                "on macOS install with: brew install tesseract"
            )
        language = tesseract_language(tesseract)
        if not language:
            raise RuntimeError(
                "Tesseract is installed but has no usable OCR language data; "
                "on macOS install language data with: brew install tesseract-lang"
            )
        fallback_text = _ocr_text_page(page, tesseract, language)
        if not fallback_text:
            continue
        page_has_salary_context = bool(_salary_context_pattern.search(fallback_text))
        page_has_table_context = bool(_ocr_table_context_pattern.search(fallback_text))
        page_looks_like_grid = _looks_like_grid_salary_table(fallback_text)
        structured_rows: list[list[object]] = []
        if page_has_table_context or structured_table_active or page_looks_like_grid:
            ocr = _ocr_page(page, tesseract, language)
            if ocr:
                context_y = _salary_context_y(ocr) if page_has_salary_context else None
                structured_rows = _ocr_money_rows(
                    ocr,
                    salary_context_active or page_has_salary_context or structured_table_active or page_looks_like_grid,
                    minimum_y=context_y,
                )
        salary_context_active = salary_context_active or page_has_salary_context
        structured_table_active = structured_table_active or bool(structured_rows)
        if structured_rows:
            out.append(
                CellTable(
                    path,
                    "ocr-money-rows",
                    page_number,
                    structured_rows,
                    "tesseract-money-table",
                )
            )
            continue
        lines = _normalized_lines(fallback_text)
        if lines:
            out.append(CellTable(path, "text-lines", page_number, [[line] for line in lines], "tesseract-text"))
    return out


def _geometry_tables(path: Path, page: fitz.Page, page_number: int) -> list[CellTable]:
    tables: list[CellTable] = []
    try:
        finder = page.find_tables()
        for table_number, table in enumerate(finder.tables, 1):
            rows = table.extract()
            rows = [["" if value is None else str(value).strip() for value in row] for row in rows]
            rows = [row for row in rows if any(row)]
            if len(rows) >= 2:
                tables.append(
                    CellTable(path, f"table-{table_number}", page_number, rows, "pymupdf-table")
                )
    except Exception:
        return []
    return tables


def _normalized_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]



def _ocr_text_page(page: fitz.Page, tesseract: str, language: str) -> str:
    """OCR a prose/list page with a mode that preserves numbered rows."""
    with tempfile.TemporaryDirectory(prefix="fedrowanie-ocr-text-") as temp_dir:
        image_path = Path(temp_dir) / "page.png"
        page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False).save(image_path)
        try:
            result = subprocess.run(
                [tesseract, str(image_path), "stdout", "-l", language, "--psm", "6"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=45,
                check=True,
            )
        except Exception:
            return ""
        return result.stdout or ""


def _looks_like_grid_salary_table(text: str) -> bool:
    """Detect dense two-column salary tables even when they have no header."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    money_lines = [line for line in lines if _money_pattern.search(line)]
    labelled = sum(bool(re.search(r"(?i)\blekarz\b|praktyka|gabinet", line)) for line in money_lines)
    if len(money_lines) >= 8:
        return labelled * 2 < len(money_lines)
    # In dense ruled tables PSM 6 can collapse dozens of physical rows into a
    # handful of OCR lines.  A few amounts on a very sparse page are enough to
    # trigger the geometry-oriented sparse-text pass; subsequent pages inherit
    # structured_table_active.
    return len(money_lines) >= 2 and len(lines) <= 10 and labelled == 0


def _ocr_page(page: fitz.Page, tesseract: str, language: str) -> dict[str, object] | None:
    with tempfile.TemporaryDirectory(prefix="fedrowanie-ocr-") as temp_dir:
        image_path = Path(temp_dir) / "page.png"
        pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
        pix.save(image_path)
        modes: dict[int, list[dict[str, object]]] = {}
        for psm in (3, 4, 11):
            try:
                result = subprocess.run(
                    [tesseract, str(image_path), "stdout", "-l", language, "--psm", str(psm), "tsv"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=45,
                    check=True,
                )
            except Exception:
                continue
            words = _parse_tsv_words(result.stdout)
            modes[psm] = words
        if not modes:
            return None

        # One higher-resolution pass is used only as a validator for a narrow
        # leading-digit ambiguity (1 vs 7) caused by ruled table lines.  Its
        # coordinates are normalized back to the 2.2x baseline so it can be
        # compared with the regular OCR candidates without changing row layout.
        refinement_candidates: list[tuple[float, float]] = []
        high_scale = 3.6
        high_path = Path(temp_dir) / "page-high.png"
        try:
            high_pix = page.get_pixmap(matrix=fitz.Matrix(high_scale, high_scale), alpha=False)
            high_pix.save(high_path)
            high_result = subprocess.run(
                [tesseract, str(high_path), "stdout", "-l", language, "--psm", "3", "tsv"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=45,
                check=True,
            )
            high_words = _parse_tsv_words(high_result.stdout)
            ratio = 2.2 / high_scale
            refinement_candidates = [
                (y * ratio, amount)
                for y, amount, _mode in _candidate_amounts(high_words, high_pix.width, 103)
            ]
        except Exception:
            refinement_candidates = []

        primary = modes.get(4) or modes.get(6) or []
        return {
            "width": pix.width,
            "modes": modes,
            "text": _words_as_text(primary),
            "refinement_candidates": refinement_candidates,
        }


def _parse_tsv_words(tsv: str) -> list[dict[str, object]]:
    words: list[dict[str, object]] = []
    for raw in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        text = (raw.get("text") or "").strip()
        if not text:
            continue
        try:
            left = int(raw["left"])
            top = int(raw["top"])
            width = int(raw["width"])
            height = int(raw["height"])
        except (KeyError, TypeError, ValueError):
            continue
        words.append(
            {
                "text": text,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "cx": left + width / 2,
                "cy": top + height / 2,
                "block": raw.get("block_num", ""),
                "paragraph": raw.get("par_num", ""),
                "line": raw.get("line_num", ""),
            }
        )
    return words


def _words_as_text(words: list[dict[str, object]]) -> str:
    lines = _group_lines(words)
    return "\n".join(_line_text(line) for line in lines)


def _group_lines(words: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for word in words:
        key = (str(word["block"]), str(word["paragraph"]), str(word["line"]))
        groups.setdefault(key, []).append(word)
    return sorted(groups.values(), key=lambda group: min(float(word["cy"]) for word in group))


def _line_text(words: list[dict[str, object]]) -> str:
    return " ".join(str(word["text"]) for word in sorted(words, key=lambda word: float(word["left"])))


def _candidate_amounts(
    words: list[dict[str, object]],
    page_width: int,
    mode: int,
) -> list[tuple[float, float, int]]:
    candidates: list[tuple[float, float, int]] = []
    for line in _group_lines(words):
        right = [word for word in line if float(word["cx"]) > 0.45 * page_width]
        if not right:
            continue
        text = _line_text(right)
        matches = list(_money_pattern.finditer(text))
        if not matches:
            continue
        token = matches[-1].group(0)
        normalized = token.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            amount = float(normalized)
        except ValueError:
            continue
        if amount < 100:
            continue
        y = sum(float(word["cy"]) for word in right) / len(right)
        candidates.append((y, amount, mode))
    return candidates


def _merge_amount_candidates(
    candidates: list[tuple[float, float, int] | tuple[float, float]],
) -> list[tuple[float, float]]:
    legacy_pairs = bool(candidates) and all(len(candidate) == 2 for candidate in candidates)
    normalized = [
        (candidate[0], candidate[1], index + 100) if len(candidate) == 2 else candidate
        for index, candidate in enumerate(candidates)
    ]
    clusters: list[list[tuple[float, float, int]]] = []
    for candidate in sorted(normalized):
        if not clusters:
            clusters.append([candidate])
            continue
        mean_y = sum(item[0] for item in clusters[-1]) / len(clusters[-1])
        if candidate[0] - mean_y > 14:
            clusters.append([candidate])
        else:
            clusters[-1].append(candidate)
    merged: list[tuple[float, float]] = []
    for cluster in clusters:
        y = sum(item[0] for item in cluster) / len(cluster)
        by_mode: dict[int, float] = {}
        for _, amount, mode in cluster:
            by_mode[mode] = amount
        counts: dict[float, int] = {}
        for amount in by_mode.values():
            key = round(amount, 2)
            counts[key] = counts.get(key, 0) + 1
        best_amount, votes = max(counts.items(), key=lambda item: (item[1], item[0]))
        if legacy_pairs:
            # Backwards-compatible two-pass behaviour used by older callers:
            # a glued LP prefix is always larger than the actual salary.
            best_amount = min(by_mode.values())
        elif votes < 2:
            # PSM 4 is the best tie-breaker for ruled tables, then PSM 3.
            best_amount = by_mode.get(4, by_mode.get(3, by_mode.get(11, best_amount)))
        merged.append((y, float(best_amount)))
    return merged



def _refine_ambiguous_leading_digit(
    ocr: dict[str, object],
    y: float,
    amount: float,
) -> float:
    """Resolve a leading 1/7 ambiguity using the high-resolution OCR pass.

    Horizontal table rules can erase the top stroke of a leading ``7`` and make
    a value such as ``76 847,50`` look like ``16 847,50`` in every normal OCR
    mode.  A replacement is accepted only when the high-resolution pass sees a
    leading ``7`` and every other integer digit plus the cents are identical.
    """
    old_digits = str(int(amount))
    if not old_digits.startswith("1") or len(old_digits) < 4:
        return amount
    candidates = ocr.get("refinement_candidates")
    if not isinstance(candidates, list) or not candidates:
        return amount
    nearby = [
        candidate
        for candidate in candidates
        if isinstance(candidate, tuple)
        and len(candidate) == 2
        and abs(float(candidate[0]) - y) <= 10
    ]
    if not nearby:
        return amount
    _candidate_y, precise = min(nearby, key=lambda candidate: abs(float(candidate[0]) - y))
    precise = float(precise)
    new_digits = str(int(precise))
    old_cents = int(round(amount * 100)) % 100
    new_cents = int(round(precise * 100)) % 100
    if (
        old_cents == new_cents
        and len(old_digits) == len(new_digits)
        and old_digits[0] == "1"
        and new_digits[0] == "7"
        and old_digits[1:] == new_digits[1:]
    ):
        return precise
    return amount


def _salary_context_y(ocr: dict[str, object]) -> float | None:
    modes = ocr["modes"]
    assert isinstance(modes, dict)
    found: list[float] = []
    for words in modes.values():
        for line in _group_lines(words):
            text = _line_text(line)
            if _salary_context_pattern.search(text):
                found.append(min(float(word["cy"]) for word in line))
    return min(found) if found else None

def _ocr_money_rows(
    ocr: dict[str, object],
    context_active: bool,
    minimum_y: float | None = None,
) -> list[list[object]]:
    if not context_active:
        return []
    page_width = int(ocr["width"])
    modes = ocr["modes"]
    assert isinstance(modes, dict)
    all_candidates: list[tuple[float, float]] = []
    for mode, words in modes.items():
        all_candidates.extend(_candidate_amounts(words, page_width, int(mode)))
    candidates = _merge_amount_candidates(all_candidates)
    candidates = [
        (y, _refine_ambiguous_leading_digit(ocr, y, amount))
        for y, amount in candidates
    ]
    if minimum_y is not None:
        candidates = [candidate for candidate in candidates if candidate[0] > minimum_y]
    if len(candidates) < 3:
        return []

    label_words = modes.get(11) or modes.get(4) or modes.get(3) or modes.get(6) or []
    result: list[list[object]] = []
    previous_y = candidates[0][0] - 120
    for index, (y, amount) in enumerate(candidates, 1):
        source = _source_for_band(label_words, page_width, previous_y + 2, y + 8)
        previous_y = y
        source = _clean_ocr_source(source)
        if not source:
            source = f"Lekarz {index}"
        result.append([source, amount])
    return result


def _source_for_band(
    words: list[dict[str, object]],
    page_width: int,
    low_y: float,
    high_y: float,
) -> str:
    selected = [
        word
        for word in words
        if low_y <= float(word["cy"]) <= high_y
        and 0.10 * page_width <= float(word["cx"]) < 0.74 * page_width
    ]
    return " ".join(_line_text(line) for line in _group_lines(selected))


def _clean_ocr_source(source: str) -> str:
    text = re.sub(r"\s+", " ", source).strip(" |[]{};,:—–-")
    anonymous = re.search(
        r"(?i)\bLekarz\s+(\d{1,3})\s+(?=(?:\d{1,3}(?:[ .]\d{3})+|\d+)[,.]\d{2})",
        text,
    )
    text = _money_pattern.sub("", text)
    text = re.sub(r"(?i)\bLekarz\s+Lekarz\b", "Lekarz", text)
    text = re.sub(r"\s+", " ", text).strip()
    if anonymous:
        return f"Lekarz {anonymous.group(1)}"
    text = re.sub(r"(?i)^l?p\.?\s*nazwa\s+", "", text)
    text = re.sub(r"(?i)^nazwa\s+", "", text)
    text = re.sub(r"\s+\d{1,3}\s*$", "", text)
    return text.strip(" |[]{};,:—–-")
