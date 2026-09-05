"""General person-name recovery from practice/company source labels."""
from __future__ import annotations

import re

from ..enrichment.person_name import extract_person_name_from_practice_text, looks_like_person_name, norm

__all__ = ["person_from_source"]

_bad = re.compile(
    r"(?i)\b(?:lekarz|specjalista|stanowisko|asystent|ordynator|rezydent|wynagrodzenie|"
    r"oddział|oddzial|chirurg|anestezjolog|internista|ginekolog)\b"
)
_business = re.compile(
    r"(?i)\b(?:indywidualna|specjalistyczna|praktyka|lekarska|gabinet|usługi|uslugi|medyczne|nzoz|zoz)\b"
)
_address_tail = re.compile(
    r"(?i)(?:,?\s+ul\.?\s|,?\s+al\.?\s|,?\s+os\.?\s|,?\s+NIP\s*:?|,?\s+REGON\s*:?|"
    r",?\s+\d{2}-\d{3}\s+[A-ZĄĆĘŁŃÓŚŹŻ])"
)
_token = r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż'’-]+"


def person_from_source(source: str) -> str:
    """Extract a confident physician name while preserving the original source label elsewhere."""
    text = norm(source)
    if not text:
        return ""
    core = _address_tail.split(text, maxsplit=1)[0].strip(" ,;|")
    direct = extract_person_name_from_practice_text(core)
    if direct and not _bad.search(direct):
        return direct

    business_match = _business.search(core)
    if business_match:
        person = _clean_person(core[: business_match.start()])
        if person:
            return person
    business_matches = list(_business.finditer(core))
    if business_matches:
        tail = core[business_matches[-1].end() :].strip(" ,;|-—–")
        person = _clean_person(tail)
        if person:
            return person
        # Practice descriptors are often followed by a name and then a brand/detail.
        match = re.match(rf"^({_token}\s+{_token}(?:\s*[-–—]\s*{_token})?)\b", tail)
        if match:
            person = _clean_person(match.group(1))
            if person:
                return person
    if not _business.search(core):
        role_person = _person_after_role(core)
        if role_person:
            return role_person
        whole = _clean_person(core)
        if whole:
            return whole

    brand = re.match(rf"^({_token}\s+{_token})(?:\s+[\"“]|\s+[A-ZĄĆĘŁŃÓŚŹŻ]{{2,}}-)", core)
    if brand:
        person = _clean_person(brand.group(1))
        if person:
            return person
    return ""


def _clean_person(value: str) -> str:
    text = norm(value).strip('"“”()[]{}.,;:- ')
    if not text or _bad.search(text):
        return ""
    tokens = text.split()
    if 2 <= len(tokens) <= 5 and all(re.fullmatch(_token, token) for token in tokens) and looks_like_person_name(text):
        return text
    return ""


def _person_after_role(value: str) -> str:
    text = re.split(r"(?i)\b(?:z-ca|zastępca|zastepca|dyrektor)\b", value, maxsplit=1)[0]
    tokens = re.findall(_token, text)
    for size in (2, 3):
        if len(tokens) < size:
            continue
        for start in range(len(tokens) - size, -1, -1):
            candidate = " ".join(tokens[start : start + size])
            if _bad.search(candidate):
                continue
            cleaned = _clean_person(candidate)
            if cleaned:
                return cleaned
    return ""
