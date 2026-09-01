"""Extract physician full names from structured response tables."""

from __future__ import annotations

import re

from ..constants import (
    PERSON_NAME_HEADER_RE,
    PERSON_NAME_MONEY_RE,
    PERSON_NAME_BAD_RE,
    PERSON_NAME_TOKEN_RE,
)


__all__ = [
    "norm",
    "split_row",
    "money_value",
    "looks_like_person_name",
    "extract_person_name_from_practice_text",
    "document_person_name_maps",
    "infer_person_name",
    "enrich_person_names",
]


def norm(s):
    """Normalize whitespace and punctuation in a text value."""
    return re.sub(r"\s+", " ", str(s or "").replace("\xa0", " ")).strip(
        " |#*_-–—:\t\r\n"
    )


def split_row(line):
    """Split a pipe-delimited source row into normalized cells."""
    s = str(line or "").strip()
    if "|" not in s:
        return []
    return [norm(x) for x in s.strip("|").split("|")]


def money_value(cell):
    """Parse a monetary value from a single table cell."""
    m = PERSON_NAME_MONEY_RE.search(str(cell or ""))
    if not m:
        return None
    t = m.group(0).replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def looks_like_person_name(s):
    """Return whether text plausibly contains a physician's full name."""
    s = norm(s)
    if (
        not s
        or len(s) > 100
        or PERSON_NAME_BAD_RE.search(s)
        or any(ch.isdigit() for ch in s)
    ):
        return False
    toks = s.split()
    if not (2 <= len(toks) <= 5):
        return False
    if not all(PERSON_NAME_TOKEN_RE.fullmatch(t) for t in toks):
        return False
    caps = sum(1 for t in toks if t[:1].isupper())
    upper = sum(
        1 for t in toks if t.upper() == t and any(c.isalpha() for c in t)
    )
    return upper == len(toks) or caps == len(toks)


# A large share of disclosed contractor rows contain the doctor's name inside
# the registered/practice name rather than in a dedicated person-name column,
# for example:
#   "Lorenc Karol lek. Indywidualna Praktyka Lekarska"
#   "Gabinet ... lek.Wiater Zygmunt"
#   "PROPIUS Leszek Jahołkowski lek. Indywidualna Praktyka Lekarska"
# The generic table parser may therefore emit ``Lekarz N`` even though a full
# name is present in the same raw row.  The patterns below deliberately use a
# medical-title/practice anchor; they are not a general company-name parser.
_PRACTICE_LEGAL_ENTITY_RE = re.compile(
    r"(?i)\b(?:sp\.?\s*z\.?\s*o\.?\s*o\.?|sp[oó][łl]ka|s\.?a\.?|sp\.?\s*k\.?)\b"
)

_PRACTICE_TITLE_RE = re.compile(
    r"(?ix)"
    r"(?:\bdr(?![A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])\.?\s*"
    r"(?:hab\.?\s*)?(?:n\.?\s*)?(?:med\.?)?\s*|"
    r"\blek(?:arz)?(?![A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])\.?\s*"
    r"(?:med\.?)?\s*)"
)

# Company/practice vocabulary is useful as a delimiter, but must not be used as
# evidence that the words after it are a person.  The previous implementation
# sometimes selected the tail after the *last* descriptor, which turned
# specialties such as "CHORÓB PŁUC" into doctor names.  We now distinguish
# business delimiters from medical-role/specialty delimiters.
_PRACTICE_BUSINESS_RE = re.compile(
    r"(?ix)\b(?:"
    r"indywidualn\w*|prywatn\w*|praktyk\w*|gabinet\w*|"
    r"niepubliczn\w*|zak[łl]ad\w*|opieki|zdrowotn\w*|us[łl]ug\w*|"
    r"centrum\w*|poradni\w*|lekarsk\w*|nzoz|zoz"
    r")\b"
)

_PRACTICE_ROLE_RE = re.compile(
    r"(?ix)\b(?:"
    r"specjalist\w*|chirurg\w*|ginekolog\w*|pediatr\w*|psychiatr\w*|"
    r"radiolog\w*|kardiolog\w*|neurolog\w*|nefrolog\w*|urolog\w*|"
    r"onkolog\w*|anestezjolog\w*|internist\w*|ortoped\w*|"
    r"traumatolog\w*|balneolog\w*|pulmonolog\w*|okulist\w*|"
    r"endokrynolog\w*|po[łl]o[żz]nictw\w*"
    r")\b"
)

# Words/word stems that cannot plausibly be components of a physician's name.
# This is deliberately medical/structural vocabulary rather than a generic
# Polish dictionary, so unusual foreign names remain accepted.
_PRACTICE_NAME_FORBIDDEN_RE = re.compile(
    r"(?ix)\b(?:"
    r"specjalist\w*|specjalizac\w*|medycyn\w*|fizykaln\w*|"
    r"chor[oó]b|p[łl]uc|terapi\w*|balneolog\w*|ortopedi\w*|"
    r"traumatolog\w*|narz[ąa]du|ruchu|psychiatri\w*|dzieci|m[łl]odzie[żz]y|"
    r"anestezjologi\w*|ginekologi\w*|po[łl]o[żz]nictw\w*|"
    r"wewn[ęe]trzn\w*|okulistyczn\w*|chirurgi\w*|naczyniow\w*|"
    r"endokrynologiczn\w*|neurolog\w*|opisy|bada[ńn]|eeg|"
    r"oddzia[łl]\w*|poradni\w*|pracowni\w*|zak[łl]ad\w*|"
    r"kierownik\w*|koordynator\w*|rezydent\w*|asystent\w*"
    r")\b"
)


def extract_person_name_from_practice_text(text: str) -> str:
    """Extract a physician name embedded in a practice/company/role label.

    Global rule, not a hospital-specific exception:
    * require an explicit clinician-title anchor (``lek.``, ``lekarz``, ``dr``),
    * prefer the fragment directly adjacent to that title,
    * cut away practice/company and specialty/role vocabulary,
    * reject specialty phrases and legal entities,
    * preserve multi-token foreign names and all-uppercase names.
    """
    s = norm(text)
    if not s or any(ch.isdigit() for ch in s):
        return ""
    if _PRACTICE_LEGAL_ENTITY_RE.search(s):
        return ""

    title_matches = list(_PRACTICE_TITLE_RE.finditer(s))
    if not title_matches:
        return ""

    post_candidates: list[str] = []
    pre_candidates: list[str] = []
    for m in title_matches:
        # Post-title form: "lek. Jan Kowalski ...".  Any role/specialty after
        # the name is a hard right boundary.  Leading specialty tokens (e.g.
        # "LEKARZ ANESTEZJOLOG PIOTR SZYMAN") are stripped conservatively.
        after = norm(s[m.end():])
        if after:
            role = _PRACTICE_ROLE_RE.search(after)
            if role and role.start() > 0:
                after = norm(after[:role.start()])
            elif role and role.start() == 0:
                after = norm(after[role.end():])
            business = _PRACTICE_BUSINESS_RE.search(after)
            if business and business.start() > 0:
                after = norm(after[:business.start()])
            elif business and business.start() == 0:
                # A practice descriptor immediately after the title does not
                # identify a person; don't scan arbitrarily far through it.
                after = ""
            cand = _clean_name_candidate(after, strip_brand=False)
            if cand:
                post_candidates.append(cand)

        # Pre-title form: "Jan Kowalski lek." or branded
        # "PROPIUS Jan Kowalski lek.".  Keep only the suffix after the last
        # business descriptor and strip a narrowly-defined likely brand.
        before = norm(s[:m.start()])
        if before:
            bmatches = list(_PRACTICE_BUSINESS_RE.finditer(before))
            if bmatches:
                before = norm(before[bmatches[-1].end():])
            cand = _clean_name_candidate(before, strip_brand=True)
            if cand:
                pre_candidates.append(cand)

    post_candidates = list(dict.fromkeys(post_candidates))
    pre_candidates = list(dict.fromkeys(pre_candidates))
    # A name directly after a professional title is stronger evidence than a
    # pre-title company/trade-name fragment (e.g. "NIEBIESKI HAMAK dr n. med.
    # AGNIESZKA BIERNACKA").  Use pre-title candidates only as fallback.
    if post_candidates:
        return min(post_candidates, key=lambda x: (len(x.split()), len(x)))
    if pre_candidates:
        return min(pre_candidates, key=lambda x: (len(x.split()), len(x)))
    return ""

def document_person_name_maps(doc):
    """Build row-to-person lookup maps from explicit name columns."""
    raw_map = {}
    idx_amount_map = {}
    name_idx = None
    for line in str(doc or "").splitlines():
        cells = split_row(line)
        if not cells:
            continue
        if all((not c) or re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        found = [
            i for i, c in enumerate(cells) if PERSON_NAME_HEADER_RE.fullmatch(norm(c))
        ]
        if found:
            name_idx = found[0]
            continue
        if (
            name_idx is not None
            and any(
                re.search(
                    r"(?i)\b(?:lp\.?|wynagrodzeni\w*|kwota|specjalizacja|oddzia[łl]|klinika|poradnia|forma zatrudn\w*)\b",
                    c,
                )
                for c in cells
            )
            and not any(re.fullmatch(r"\d+", c) for c in cells[:2])
        ):
            name_idx = None
            continue
        if name_idx is None or name_idx >= len(cells):
            continue
        name = norm(cells[name_idx])
        if not looks_like_person_name(name):
            name = extract_person_name_from_practice_text(name)
        if not name:
            continue
        raw_map[" | ".join(cells)] = name
        idx = None
        for c in cells[:2]:
            if re.fullmatch(r"\d+", c):
                idx = int(c)
                break
        amounts = [money_value(c) for c in cells]
        amounts = [x for x in amounts if x is not None]
        if idx is not None and amounts:
            idx_amount_map[(idx, int(round(max(amounts, key=abs) * 100)))] = name
    return raw_map, idx_amount_map


def infer_person_name(raw_row, existing_spec="", unit=""):
    """Infer a physician name from a structured row when headers are unavailable."""
    cells = split_row(raw_row)
    if not cells:
        return ""
    candidates = []
    unit_cf = norm(unit).casefold()
    for c in cells:
        if not c or re.fullmatch(r"\d+\.?", c) or money_value(c) is not None:
            continue
        if unit_cf and norm(c).casefold() == unit_cf:
            # Unit inference can occasionally copy an entire contractor cell
            # into ``organizational_unit``.  Do not let that hide a physician
            # name embedded in the same practice/company label.
            practice_name = extract_person_name_from_practice_text(c)
            if practice_name:
                candidates.append(practice_name)
            continue
        if looks_like_person_name(c):
            candidates.append(norm(c))
            continue
        practice_name = extract_person_name_from_practice_text(c)
        if practice_name:
            candidates.append(practice_name)
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) == 1:
        return candidates[0]
    sp = norm(existing_spec)
    if looks_like_person_name(sp):
        return sp
    return ""

# Known trade-name pattern: an all-caps brand followed by a normally-cased
# doctor name, or a TitleCase token ending in "med" followed by a normally-cased
# name.  Do not strip a first token when the whole candidate is uppercase;
# that would corrupt valid names such as "MOHAMED RIYAD SULIMA".
def enrich_person_names(rows, doc: str):
    """Enrich doctor/source names without changing salary facts or recipient type.

    This is intentionally part of the person-name enrichment layer, not the
    orchestration pipeline.  The operation may update only identity metadata
    (``doctor_name``, selected synthetic/practice-labelled ``source_name`` and
    an exact false-positive ``specialization``).  It must preserve row count,
    row order, net/gross compensation and the pre-existing ``recipient_type``.
    """
    before = tuple(
        (
            id(row),
            row.case_pk,
            row.institution_pk,
            row.page_number,
            row.raw_row,
            row.net_compensation,
            row.gross_compensation,
            getattr(row, "recipient_type", None),
        )
        for row in rows
    )

    raw_name_map, idx_name_map = document_person_name_maps(doc)
    for row in rows:
        key = " | ".join(
            norm(x)
            for x in str(row.raw_row or "").strip().strip("|").split("|")
        )
        person = raw_name_map.get(key, "")
        amount = (
            row.gross_compensation
            if row.gross_compensation is not None
            else row.net_compensation
        )
        m_idx = re.match(r"^\s*(\d+)\b", str(row.raw_row or ""))
        if not person and m_idx and amount is not None:
            person = idx_name_map.get(
                (int(m_idx.group(1)), int(round(float(amount) * 100))), ""
            )
        if not person:
            person = infer_person_name(
                row.raw_row, row.specialization, row.organizational_unit
            )
        if not person:
            continue

        row.doctor_name = person

        # Generic table layouts often synthesize ``Lekarz N`` even though the
        # contractor/practice cell contains the physician's actual full name.
        # Once conservatively recovered, expose that name as ``source_name``.
        source = norm(row.source_name)
        if (
            re.fullmatch(r"(?i)Lekarz\s+\d{1,4}", source)
            or extract_person_name_from_practice_text(source)
        ):
            row.source_name = person

        # Historical generic parsing could copy a person name into the
        # specialization field.  Clear only an exact duplicate.
        if (
            (row.specialization or "").strip()
            and norm(row.specialization).casefold() == norm(person).casefold()
        ):
            row.specialization = ""

    after = tuple(
        (
            id(row),
            row.case_pk,
            row.institution_pk,
            row.page_number,
            row.raw_row,
            row.net_compensation,
            row.gross_compensation,
            getattr(row, "recipient_type", None),
        )
        for row in rows
    )
    if after != before:
        raise RuntimeError(
            "person-name enrichment changed row count/order, compensation, "
            "or recipient_type"
        )
    return rows


def _strip_likely_brand_prefix(tokens: list[str]) -> list[str]:
    if len(tokens) < 3:
        return tokens
    first = tokens[0]
    tail = tokens[1:]
    tail_all_upper = all(
        t.upper() == t and any(ch.isalpha() for ch in t) for t in tail
    )
    tail_titleish = all(
        (t[:1].isupper() and not t.isupper()) or "-" in t for t in tail
    )
    first_is_brand = (
        (first.isupper() and len(first) >= 5 and not tail_all_upper)
        or (
            first.casefold().endswith("med")
            and not first.isupper()
            and tail_titleish
        )
    )
    return tail if first_is_brand else tokens


def _looks_like_anchored_person_name(s: str) -> bool:
    """Validate a title-adjacent full name without assuming Polish casing."""
    s = norm(s)
    if (
        not s
        or len(s) > 100
        or PERSON_NAME_BAD_RE.search(s)
        or _PRACTICE_NAME_FORBIDDEN_RE.search(s)
        or any(ch.isdigit() for ch in s)
    ):
        return False
    toks = s.split()
    if not (2 <= len(toks) <= 5):
        return False
    if not all(PERSON_NAME_TOKEN_RE.fullmatch(t) for t in toks):
        return False

    upper = sum(
        1 for t in toks if t.upper() == t and any(c.isalpha() for c in t)
    )
    title = sum(1 for t in toks if t[:1].isupper() and t[1:] != t[1:].upper())
    lower = sum(1 for t in toks if t.islower())

    # Normal title case, all-caps source tables, or a single OCR-lowercased name
    # token next to otherwise person-like tokens.  Reject generic phrases such
    # as "opisy badań EEG" (two lowercase common-noun tokens).
    return (
        upper == len(toks)
        or title == len(toks)
        or (lower <= 1 and upper + title + lower == len(toks) and upper + title >= 1)
    )


def _clean_name_candidate(text: str, *, strip_brand: bool) -> str:
    """Clean a title-adjacent fragment and keep only a conservative full name."""
    s = norm(text)
    if not s:
        return ""

    s = norm(_PRACTICE_TITLE_RE.sub(" ", s))
    s = re.sub(r"^[.,;:/\-–—]+|[.,;:/\-–—]+$", "", s).strip()
    if not s:
        return ""

    # Specialty/role vocabulary after a person is always a boundary.
    role = _PRACTICE_ROLE_RE.search(s)
    if role and role.start() > 0:
        s = norm(s[:role.start()])
    elif role and role.start() == 0:
        s = norm(s[role.end():])

    toks = [t.strip(".,;:()[]{}") for t in s.split()]
    toks = [t for t in toks if t]
    if strip_brand:
        toks = _strip_likely_brand_prefix(toks)

    candidate = norm(" ".join(toks))
    return candidate if _looks_like_anchored_person_name(candidate) else ""
