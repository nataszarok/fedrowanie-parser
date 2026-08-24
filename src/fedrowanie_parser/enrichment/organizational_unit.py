
from __future__ import annotations
import re

UNIT_RE = re.compile(
    r'(?i)\b(?:pododdzia[łl]|oddzia[łl]|klinika|pracownia|poradnia|'
    r'szpitalny oddzia[łl] ratunkowy|SOR\b|izba przyj[ęe][ćc]|'
    r'nocna i [śs]wi[ąa]teczna opieka(?: zdrowotna| medyczna)?|'
    r'o[śs]rodek rehabilitacji|zak[łl]ad\b|\bkl\.\s*|^o\.\s*)'
)
CONTACT_RE = re.compile(r'(?i)\b(?:tel\.?|fax|e-?mail|www\.|ul\.|telefon)\b')
MONEY_RE = re.compile(r'\d{1,3}(?:[ .]\d{3})*[,.]\d{2}')
ROLE_RE = re.compile(r'(?i)^(?:koordynator|zast[ęe]pca koordynatora|z-ca koordynatora|'
                     r'ordynator|zast[ęe]pca ordynatora|kierownik|p\.?o\.?.*)$')

def norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

def looks_like_unit(s):
    s=norm(s)
    if not s or len(s)>180 or CONTACT_RE.search(s) or MONEY_RE.search(s):
        return False
    if re.search(r'(?i)\b(?:lp\.?|l\.p\.?|wynagrodzeni\w*|forma zatrudn\w*|'
                 r'nazwisko|imi[ęe]|do kiedy zatrudniony|kwota)\b',s):
        return False
    if re.fullmatch(r'(?i)(?:lekarz\s+)?(?:kierownik|asystent|zast[ęe]pca|z-ca).*oddzia[łl]u',s):
        return False
    return bool(UNIT_RE.search(s))

def unit_from_raw_row(raw):
    cells=[norm(x) for x in str(raw or '').strip().strip('|').split('|')]
    # Explicit schema frequently used in responses:
    # lekarz N | nazwa komórki organizacyjnej | kwota | rodzaj umowy
    if len(cells)==4:
        first, second, third, fourth=cells
        if (
            re.fullmatch(r'(?i)lekarz\s+\d+',first)
            and second
            and MONEY_RE.search(third)
            and re.fullmatch(r'(?i)(?:umowa zlecenia|umowa o prac[ęe]|kontrakt|cywilnoprawna)',fourth)
        ):
            return second
    # Otherwise prefer an explicit unit-bearing cell.
    for c in cells:
        if looks_like_unit(c):
            return c
    return ''

def split_existing_specialization(spec):
    """
    Existing parser sometimes stores 'ODDZIAŁ ... — Lekarz specjalista'
    in specjalizacja. Split this into organizational unit + true specialization.
    """
    s=norm(spec)
    if not s:
        return '', ''
    if ' — ' in s:
        left,right=s.split(' — ',1)
        if looks_like_unit(left):
            return norm(left), norm(right)
    if looks_like_unit(s):
        # A pure organizational-unit value is not a medical specialization.
        return s, ''
    return '', s

def section_unit_for_row(doc, raw_row):
    text=str(doc or '')
    raw=str(raw_row or '')
    p=text.find(raw)
    if p<0:
        return ''
    # Search only a local block. A real section heading must be a standalone
    # line, not letterhead/contact information, and must be after the previous
    # salary-table boundary when possible.
    pre=text[max(0,p-5000):p]
    lines=pre.splitlines()
    barrier_re=re.compile(
        r'(?i)(?:^|\|)\s*(?:lp\.?|l\.p\.?|lekarze?\b|nazwisko\b|imi[ęe]\b|'
        r'wynagrodzeni\w*\b|przych[oó]d\b|kwota\b)|'
        r'za[łl][ąa]cznik\s+nr\b'
    )
    for line in reversed(lines[-80:]):
        s=norm(line)
        if not s:
            continue
        # A table/title boundary resets an older organizational heading. This
        # prevents letterhead text such as "Izba Przyjęć" from leaking into a
        # later salary table.
        if barrier_re.search(s) and not looks_like_unit(s):
            break
        if not looks_like_unit(s):
            continue
        # reject prose sentences mentioning an oddział incidentally
        if len(s.split())>16 and not s.endswith(':'):
            continue
        if re.search(r'(?i)\b(?:tutejszy|podmiot|informuje|świadczenia|zatrudnion|'
                     r'udziela|oddziały:)\b',s):
            continue
        return s
    return ''

def infer_unit_and_specialization(doc, raw_row, existing_spec):
    # Highest confidence: unit is literally a column/value in the record.
    raw_unit=unit_from_raw_row(raw_row)
    old_unit, cleaned_spec=split_existing_specialization(existing_spec)
    if raw_unit:
        return raw_unit, cleaned_spec
    if old_unit:
        return old_unit, cleaned_spec
    sec=section_unit_for_row(doc,raw_row)
    return sec, cleaned_spec
