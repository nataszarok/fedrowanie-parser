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
    "extract_person_name_from_source_label",
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


_DIRECT_NAME_NONPERSON_RE = re.compile(
    r"(?ix)\b(?:"
    r"lekarz\w*|lekarsk\w*|specjali\w*|specjalizac\w*|"
    r"praktyk\w*|gabinet\w*|przychodni\w*|poradni\w*|"
    r"oddzia[łl]\w*|klinika\w*|pracowni\w*|zak[łl]ad\w*|"
    r"chirurg\w*|ginekolog\w*|pediatr\w*|psychiatr\w*|"
    r"radiolog\w*|kardiolog\w*|neurolog\w*|nefrolog\w*|"
    r"urolog\w*|onkolog\w*|anestez\w*|ortoped\w*|"
    r"medycyn\w*|medyczn\w*|medical|wielospecjalist\w*|"
    r"indywidualn\w*|prywatn\w*|us[łl]ug\w*|"
    r"wynagrodzeni\w*|kwot\w*|brutto|netto|etat\w*"
    r")\b"
)


_PERSON_PLACEHOLDER_RE = re.compile(
    r"(?ix)^(?:x{2,}|anonim(?:owy|owa)?|nieznany|brak)(?:\s+(?:x{2,}|anonim(?:owy|owa)?|nieznany|brak))*$"
)


def looks_like_person_name(s):
    """Return whether text plausibly contains a physician's full name.

    Initials and anonymisation placeholders are intentionally rejected here;
    they belong in ``doctor_initials``/source provenance, not ``doctor_name``.
    """
    s = norm(s)
    if (
        not s
        or len(s) > 100
        or PERSON_NAME_BAD_RE.search(s)
        or _DIRECT_NAME_NONPERSON_RE.search(s)
        or _PERSON_PLACEHOLDER_RE.fullmatch(s)
        or any(ch.isdigit() for ch in s)
    ):
        return False
    toks = s.split()
    if not (2 <= len(toks) <= 5):
        return False
    if not all(PERSON_NAME_TOKEN_RE.fullmatch(t) for t in toks):
        return False
    # Two or more bare initials ("K K", "M B", also dotted forms after
    # normalization) are anonymised identifiers, not a full person name.
    if all(len(re.sub(r"[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]", "", t)) == 1 for t in toks):
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

_EMPLOYMENT_SUFFIX_RE = re.compile(
    r"(?ix)\s*[-–—,;:]\s*(?:na\s+)?\d+\s*/\s*\d+\s*(?:etatu|etat\w*)\b.*$"
)

_SOURCE_PRACTICE_PREFIX_RE = re.compile(
    r"(?ix)^(?:indywidualn\w*|prywatn\w*)\s+praktyk\w*\s+lekarsk\w*\s+(.+)$"
)

_SOURCE_GABINET_SUFFIX_RE = re.compile(
    r"(?ix)^(.+?)\s+(?:specjalistyczn\w*\s+)?gabinet\w*\b.*$"
)

# Broad *delimiter* vocabulary for sole-practice labels.  Unlike
# ``looks_like_person_name`` this is only used after we already know the whole
# source label contains non-person context; the surviving segment must still
# pass the strict person-name validator.  Abbreviations cover common OCR/table
# forms such as ``Indyw.Pr.Lek.``, ``Gab.Urolog.`` and ``Usł.Med.``.
_SOURCE_DESCRIPTOR_RE = re.compile(
    r"(?ix)(?:"
    r"\b(?:indywidualn\w*|indywid\.?|indyw\.?|prywatn\w*|pryw\.?|"
    r"specjali\w*|spec\.?|praktyk\w*|prakt\.?|"
    r"gabinet\w*|gab\.?|lekarsk\w*|"
    r"przychodni\w*|poradni\w*|medical|intermed|"
    r"pomoc|usg|us[łl]ug\w*|us[łl]\.?|medyczn\w*|med\.?|"
    r"ginekolog\w*|po[łl]o[żz]nicz\w*|psychiatr\w*|neurolog\w*|pediatr\w*|"
    r"ortoped\w*|urolog\w*|chirurg\w*|kardiolog\w*|radiodiagnost\w*"
    r")\b"
    r")"
)


def _person_from_descriptor_label(text: str) -> str:
    """Extract a person segment from a sole-practice/gabinet source label."""
    s = norm(text)
    if not s or not _SOURCE_DESCRIPTOR_RE.search(s):
        return ""

    parts = _SOURCE_DESCRIPTOR_RE.split(s)
    candidates: list[tuple[int, int, str]] = []
    for part_idx, part in enumerate(parts):
        fragment = norm(re.sub(r"^[.,;:/\-–—]+|[.,;:/\-–—]+$", "", part))
        if not fragment:
            continue

        if looks_like_person_name(fragment):
            candidates.append((part_idx, len(fragment.split()), fragment))
            continue

        # Long practice descriptions often end in the proprietor's name, e.g.
        # "... na podstawie umowy ... DARIUSZ BULINSKI".  Consider only suffix
        # windows, so generic prose before the name cannot become identity.
        toks = [t.strip(".,;:()[]{}„”\"") for t in fragment.split()]
        toks = [t for t in toks if t]
        toks = _strip_likely_brand_prefix(toks)
        for width in range(min(5, len(toks)), 1, -1):
            candidate = norm(" ".join(toks[-width:]))
            if looks_like_person_name(candidate):
                candidates.append((part_idx, width, candidate))
                break

    if not candidates:
        return ""
    # Prefer the right-most surviving fragment (person follows practice text in
    # prefix labels), then the most informative name within that fragment.
    return max(candidates, key=lambda x: (x[0], x[1], len(x[2])))[2]


def _clean_source_identity_label(text: str) -> str:
    """Remove address/registry tails while preserving the source value itself."""
    s = norm(text)
    if not s:
        return ""

    # OCR frequently inserts spaces around a hyphen inside compound surnames.
    s = re.sub(
        r"(?<=[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])\s*-\s*(?=[A-ZĄĆĘŁŃÓŚŹŻ])",
        "-",
        s,
    )

    # Explicit street/registry metadata is never part of a physician name.
    s = re.split(r"(?i)\s+ul\.?\s+|\s+NIP\s*:|\s+REGON\s*:", s, maxsplit=1)[0]

    # A comma commonly starts an address/registry tail, or separates a person
    # from a following practice descriptor ("Kowalski Jan, Indywidualna ...").
    if "," in s:
        head, tail = s.split(",", 1)
        if re.search(r"\d", tail) or _SOURCE_DESCRIPTOR_RE.search(tail) or re.search(
            r"(?i)\b(?:NIP|REGON|ul\.)\b", tail
        ):
            s = head
    return norm(s)


def extract_person_name_from_source_label(text: str) -> str:
    """Recover a full person name from a parser source label conservatively.

    ``source_name`` is intentionally preserved as provenance.  This helper only
    derives ``doctor_name`` from labels that are already a plausible full name
    or from common sole-practice labels with an unambiguous person fragment.
    """
    s = _clean_source_identity_label(text)
    if not s:
        return ""

    anchored = extract_person_name_from_practice_text(s)
    if anchored:
        return anchored

    if _PRACTICE_LEGAL_ENTITY_RE.search(s):
        return ""

    m = _SOURCE_PRACTICE_PREFIX_RE.match(s)
    if m:
        candidate = norm(m.group(1))
        if looks_like_person_name(candidate):
            return candidate

    m = _SOURCE_GABINET_SUFFIX_RE.match(s)
    if m:
        candidate = norm(m.group(1))
        if looks_like_person_name(candidate):
            return candidate

    descriptor_name = _person_from_descriptor_label(s)
    if descriptor_name:
        return descriptor_name

    direct = norm(_EMPLOYMENT_SUFFIX_RE.sub("", s))
    if looks_like_person_name(direct):
        return direct

    return ""


def document_person_name_maps(doc):
    """Build row-to-person lookup maps from explicit name columns.

    Besides a single "Imię i nazwisko" column, support tables that expose
    surname and given name in two adjacent/dedicated columns (e.g.
    ``Nazwisko | Imię``).  When the headers identify both components, the
    canonical value is emitted as ``Nazwisko Imię``.
    """
    raw_map = {}
    idx_amount_map = {}
    name_idx = None
    split_name_idxs = None
    for line in str(doc or "").splitlines():
        cells = split_row(line)
        if not cells:
            continue
        if all((not c) or re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue

        surname_idxs = [
            i
            for i, c in enumerate(cells)
            if re.fullmatch(r"(?i)nazwisko(?:\s+lekarza)?", norm(c))
        ]
        given_idxs = [
            i
            for i, c in enumerate(cells)
            if re.fullmatch(r"(?i)imi[ęe](?:\s+lekarza)?", norm(c))
        ]
        if surname_idxs and given_idxs:
            split_name_idxs = (surname_idxs[0], given_idxs[0])
            name_idx = None
            continue

        found = [
            i for i, c in enumerate(cells) if PERSON_NAME_HEADER_RE.fullmatch(norm(c))
        ]
        if found:
            name_idx = found[0]
            split_name_idxs = None
            continue

        if (
            (name_idx is not None or split_name_idxs is not None)
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
            split_name_idxs = None
            continue

        name = ""
        if split_name_idxs is not None:
            surname_idx, given_idx = split_name_idxs
            if max(given_idx, surname_idx) >= len(cells):
                continue
            given = norm(cells[given_idx])
            surname = norm(cells[surname_idx])
            candidate = norm(f"{surname} {given}")
            if looks_like_person_name(candidate):
                name = candidate
        elif name_idx is not None:
            if name_idx >= len(cells):
                continue
            name = norm(cells[name_idx])
            if not looks_like_person_name(name):
                name = extract_person_name_from_practice_text(name)

        if not name:
            continue
        raw_map[" | ".join(cells)] = name
        idx = None
        for c in cells[:2]:
            if re.fullmatch(r"\d+\.?", c):
                idx = int(c.rstrip("."))
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
    (``doctor_name`` and an exact false-positive ``specialization``).
    ``source_name`` remains untouched as provenance. It must preserve row count,
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
        # Do not preserve parser/enrichment false positives merely because the
        # field is already populated.  ``doctor_name`` is semantic identity, so
        # an existing value must itself be a plausible person or be reducible
        # from a sole-practice label to one.  Otherwise clear it and let the
        # normal inference chain try again from raw/source context.
        existing = norm(getattr(row, "doctor_name", ""))
        if existing and not looks_like_person_name(existing):
            recovered = extract_person_name_from_source_label(existing)
            row.doctor_name = recovered if recovered else ""

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
            person = extract_person_name_from_source_label(row.source_name)
        if not person:
            continue

        row.doctor_name = person

        # Historical generic parsing could copy a person name into the
        # specialization field.  Clear only an exact duplicate.
        if (
            (row.specialization or "").strip()
            and norm(row.specialization).casefold() == norm(person).casefold()
        ):
            row.specialization = None

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
    # Two or more bare initials ("K K", "M B", also dotted forms after
    # normalization) are anonymised identifiers, not a full person name.
    if all(len(re.sub(r"[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]", "", t)) == 1 for t in toks):
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
