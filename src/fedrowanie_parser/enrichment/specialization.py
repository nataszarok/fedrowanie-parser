"""Infer medical specialization from row-level textual context."""


from __future__ import annotations

from ..constants import (
    SPECIALIZATION_PATTERNS,
    SPECIALIZATION_GENERIC_ONLY_RE,
)
import re


__all__ = [
    "infer_specialization_from_raw_row",
]


def infer_specialization_from_raw_row(
    raw_row, existing_spec="", organizational_unit=""
):
    """
    Conservative record-level specialization extraction.
    Existing non-empty specialization always wins.
    Returns (specialization, evidence) or None.
    """
    existing = _norm(existing_spec)
    role_only = False
    # Roles/functions are not medical specialties.
    if existing and re.fullmatch(
        r"(?i)(?:lekarz\s+)?(?:asystent(?:\s+oddzia[łl]u)?|"
        r"kierownik(?:\s+oddzia[łl]u)?|koordynator|"
        r"zast[ęe]pca\s+(?:koordynatora|ordynatora)|z-ca\s+(?:koordynatora|ordynatora)|"
        r"ordynator|rezydent|lekarz medycyny)",
        existing,
    ):
        existing = ""
        role_only = True
    if existing:
        return None

    unit = _norm(organizational_unit)

    raw = _clean_candidate(raw_row)
    if not raw:
        return None

    # Evaluate text cells separately. A cell explicitly describing an
    # organizational unit must not create a physician specialty.
    cells = [_norm(x) for x in str(raw_row or "").strip().strip("|").split("|")]
    unit_cell_re = re.compile(
        r"(?i)(?:\b(?:oddzia[łl]|pododdzia[łl]|klinika|pracownia|poradnia|zak[łl]ad|"
        r"szpitalny oddzia[łl] ratunkowy|SOR\b|izba przyj[ęe][ćc]|o[śs]rodek)\b|"
        r"^\s*kl\.\s*|^\s*o\.\s*)"
    )
    candidate_cells = []
    for c in cells:
        if not c:
            continue
        # A structurally identified organizational-unit cell can describe the
        # specialty of the clinic without proving the doctor's specialization.
        if unit and _norm(c).casefold() == unit.casefold():
            continue
        if unit_cell_re.search(c):
            continue
        # Skip pure index / money / contract cells.
        if re.fullmatch(r"\d+", c):
            continue
        if re.search(r"\d{1,3}(?:[ .]\d{3})*[,.]\d{2}", c):
            continue
        if re.fullmatch(
            r"(?i)(?:umowa zlecenia|umowa o prac[ęe]|kontrakt|cywilnoprawna)", c
        ):
            continue
        candidate_cells.append(c)

    # For structured table rows, excluded cells stay excluded. Falling back
    # to the whole row would re-import unit names such as "Poradnia Ginekologiczna".
    # Whole-row fallback is allowed only for unstructured/plain-text records.
    if candidate_cells:
        search_text = " | ".join(candidate_cells)
    elif len(cells) <= 1:
        search_text = raw
    else:
        return None
    hits = []
    for label, pat in SPECIALIZATION_PATTERNS:
        if pat.search(search_text):
            hits.append(label)

    # Deduplicate nested labels.
    cleaned = []
    for h in hits:
        if h == "radiologia" and "radiologia i diagnostyka obrazowa" in hits:
            continue
        if h == "psychiatria" and "psychiatria dzieci i młodzieży" in hits:
            continue
        if h == "anestezjologia" and "anestezjologia i intensywna terapia" in hits:
            continue
        if h == "chirurgia" and any(x.startswith("chirurgia ") for x in hits):
            continue
        if h == "rehabilitacja" and "rehabilitacja medyczna" in hits:
            continue
        if h == "onkologia" and "onkologia kliniczna" in hits:
            continue
        if h == "ortopedia" and "ortopedia i traumatologia" in hits:
            continue
        if h == "ginekologia" and "ginekologia i położnictwo" in hits:
            continue
        cleaned.append(h)
    hits = list(dict.fromkeys(cleaned))

    if not hits:
        if role_only:
            return "", "usunięto rolę/funkcję z pola specjalizacja"
        return None

    # Prefer a concise canonical label. If two independent specialties are
    # explicitly present, preserve both.
    if len(hits) == 1:
        spec = hits[0]
    else:
        # Preserve at most two strong explicit specialties.
        spec = " / ".join(hits[:2])
    return spec, f"specjalizacja z raw_row: {spec}"


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip(
        " |#*_-–—:\t\r\n"
    )


def _clean_candidate(raw):
    s = _norm(raw)
    # Remove obvious amount fragments / index cells, keep wording.
    s = re.sub(
        r"\b\d{1,3}(?:[ .]\d{3})*[,.]\d{2}\s*(?:z[łl]|pln)?\b", " ", s, flags=re.I
    )
    s = re.sub(r"^\s*\d+\s*\|\s*", "", s)
    return _norm(s)
