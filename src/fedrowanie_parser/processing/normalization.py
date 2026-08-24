"""Shared normalization, money parsing, regexes and semantic helpers."""
from __future__ import annotations

from ..constants import *
import argparse
import csv
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

try:
    from ..special_cases.monthly_ledger import (
        parse_monthly_ledger,
        aggregate_transactions,
        merge_local_person_variants,
    )
except ImportError:
    parse_monthly_ledger = None
    aggregate_transactions = None
    merge_local_person_variants = None

try:
    from ..enrichment.attachment_contract import contract_zones, match_row_to_zone
except ImportError:
    contract_zones = None
    match_row_to_zone = None

try:
    from ..special_cases.multi_contract_columns import infer_contract_from_multi_columns, split_multi_contract_amounts, expand_stacked_contract_headers, document_multi_contract_row_map
except ImportError:
    infer_contract_from_multi_columns = None
    split_multi_contract_amounts = None
    expand_stacked_contract_headers = None
    document_multi_contract_row_map = None

try:
    from ..enrichment.contract_semantic import infer_contract_from_record_and_section
except ImportError:
    infer_contract_from_record_and_section = None

try:
    from ..enrichment.organizational_unit import infer_unit_and_specialization
except ImportError:
    infer_unit_and_specialization = None

try:
    from ..enrichment.specialization import infer_specialization_from_raw_row
except ImportError:
    infer_specialization_from_raw_row = None

try:
    from ..enrichment.unit_column import (
        document_unit_row_map,
        document_unit_index_amount_map,
        shifted_row_unit_candidate,
        section_unit_map,
        inline_ocr_section_unit,
    )
except ImportError:
    document_unit_row_map = None
    document_unit_index_amount_map = None
    shifted_row_unit_candidate = None
    section_unit_map = None
    inline_ocr_section_unit = None

try:
    from ..special_cases.section_salary_list import parse_section_salary_list
except ImportError:
    parse_section_salary_list = None

try:
    from ..enrichment.person_name import document_person_name_maps, infer_person_name
except ImportError:
    document_person_name_maps = None
    infer_person_name = None

try:
    from ..enrichment.doctor_status import extract_status
except ImportError:
    extract_status = None

try:
    from ..enrichment.doctor_initials import document_initial_maps, infer_initials_from_row
except ImportError:
    document_initial_maps = None
    infer_initials_from_row = None



from ..models import SalaryRow

def norm_space(s: str) -> str:
    return re.sub('\\s+', ' ', (s or '').replace('\xa0', ' ')).strip(' |\t\r\n')

def parse_money(token: str) -> Optional[float]:
    if not token:
        return None
    s = token.lower().replace('zł', '').replace('pln', '').replace('\xa0', ' ').strip()
    s = s.replace(' ', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s:
        if re.fullmatch('\\d{1,3}(?:\\.\\d{3})+', s):
            s = s.replace('.', '')
        elif re.fullmatch('\\d{1,7}\\.\\d{1,2}', s):
            pass
    try:
        value = float(s)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value

def money_cells(text: str) -> list[tuple[str, float]]:
    out = []
    for m in MONEY_TOKEN.finditer(text or ''):
        tok = m.group(0)
        val = parse_money(tok)
        if val is not None:
            out.append((tok, val))
    return out

def money_values(text: str) -> list[float]:
    return [val for _, val in money_cells(text)]

def is_metadata_or_date(line: str) -> bool:
    l = norm_space(line)
    if DATE_RE.search(l) or ISO_DATE_RE.search(l):
        return True
    if PHONEISH_RE.search(l) and (not SPECIALIZATION_WORDS.search(l)):
        return True
    if re.search('(?i)\\b(?:godzina|data\\s+odebrania|wygenerowano|załącznik\\s+nr|strona\\s+\\d+)\\b', l):
        return True
    return False

def mentions_other_year(line: str) -> bool:
    years = {int(x) for x in YEAR_OTHER_RE.findall(line or '')}
    return bool(years and YEAR not in years)

def is_summary_row(line: str) -> bool:
    l = norm_space(line)
    if not SUMMARY_RE.search(l):
        return False
    if PERSON_TOTAL_RE.search(l):
        return False
    if re.match('(?i)^(?:\\|\\s*)?(?:lp\\.?\\s*)?\\d+\\s*[|;,:-].*\\blekarz\\b', l):
        return False
    return True

def detect_contract(text: str, fallback: str='') -> str:
    t = text or ''
    has_work = bool(re.search('(?i)umow[ayę]\\s+o\\s+prac[ęe]|etat|stosunek\\s+pracy', t))
    has_order = bool(re.search('(?i)umow[ayę]\\s+zlecen|zlecenie', t))
    has_contract = bool(re.search('(?i)kontrakt|cywilno[- ]?prawn|działalnoś[ćc]\\s+gospodar', t))
    if has_work and has_order and (not has_contract):
        return 'umowa o pracę / umowa zlecenia'
    if has_contract and (not has_work) and (not has_order):
        return 'kontrakt/cywilnoprawna'
    if has_order and (not has_work):
        return 'umowa zlecenia'
    if has_work and (not has_order):
        return 'umowa o pracę'
    for pat, label in CONTRACT_PATTERNS:
        if pat.search(t):
            return label
    return fallback

def amount_kind(text: str) -> str:
    if NET_RE.search(text or '') and (not GROSS_RE.search(text or '')):
        return 'netto'
    return 'brutto'

def clean_header(h: str) -> str:
    return norm_space(re.sub('[*_#]', '', h)).lower()

def split_markdown_row(line: str) -> list[str]:
    if '|' not in line:
        return []
    return [norm_space(x) for x in line.strip().strip('|').split('|')]

def split_md_row(line: str) -> list[str]:
    return split_markdown_row(line)

def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all((not x or re.fullmatch(':?-{3,}:?', x) for x in cells))

def header_has_money_context(headers: list[str]) -> bool:
    h = ' '.join(headers)
    return bool(re.search('(?i)wynagrod|kwota|brutto|netto|2025|zł|pln|kontrakt|zlecen|umowa', h))

def infer_name_and_spec(cells: list[str], headers: list[str], idx_col: Optional[int]) -> tuple[str, str]:
    name = ''
    spec = ''
    for i, (c, h) in enumerate(zip(cells, headers)):
        if not c or i == idx_col:
            continue
        if re.search('(?i)nazw|imi[ęe]|inicja|lekarz|kontrahent|kartotek', h):
            if not money_cells(c):
                name = c
        if re.search('(?i)specjal|stanow|oddział|klinika|zakład|poradnia', h):
            if not money_cells(c):
                spec = c
    text_candidates = []
    for i, c in enumerate(cells):
        if i == idx_col or not c or money_cells(c):
            continue
        if re.fullmatch('\\d+', c):
            continue
        text_candidates.append(c)
    if not name and text_candidates:
        for c in text_candidates:
            if re.fullmatch('(?:[A-ZĄĆĘŁŃÓŚŹŻ]\\.?\\s*){2,4}', c) or re.search('(?i)\\blekarz\\b', c):
                name = c
                break
    if not spec and text_candidates:
        for c in text_candidates:
            if SPECIALIZATION_WORDS.search(c) and c != name:
                spec = c
                break
    return (name, spec)

def parse_idx(cells: list[str], headers: list[str]) -> tuple[Optional[int], Optional[int]]:
    for i, h in enumerate(headers):
        if re.search('(?i)^(?:lp\\.?|l\\.p\\.?|nr|numer)$', h):
            m = re.search('\\d+', cells[i] if i < len(cells) else '')
            return (int(m.group()) if m else None, i)
    if cells:
        m = re.fullmatch('\\s*(\\d{1,4})\\s*[.):]?\\s*', cells[0])
        if m:
            return (int(m.group(1)), 0)
    return (None, None)

def label_for_row(idx: Optional[int], name: str) -> str:
    if name:
        return name
    return f'Lekarz {idx}' if idx is not None else 'Lekarz'

def table_should_be_excluded(headers: list[str], context: str) -> tuple[bool, str]:
    h = ' '.join((clean_header(x) for x in headers))
    c = norm_space(context).lower()
    if (re.search(r'(?i)liczba\s+lekarzy|liczba\s+osób|liczba\s+osob', h)
            and re.search(r'(?i)łączna\s+kwota\s+wynagrodze[nń]|laczna\s+kwota\s+wynagrodze[nń]|suma\s+wynagrodze[nń]', h)):
        return (True, 'group_count_total_salary')
    roman_month_cols = sum((1 for x in headers if re.fullmatch('(?i)(?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)', clean_header(x))))
    has_annual_total = bool(re.search('(?i)(?:łącznie|lacznie|suma|wynagrodzenie).*2025|2025.*(?:łącznie|lacznie|suma)', h))
    if roman_month_cols >= 3 and (not has_annual_total):
        return (True, 'monthly_or_periodic_rates')
    has_min = bool(re.search('(?i)\\b(?:minimum|minimaln|min\\.)\\b', h))
    has_max = bool(re.search('(?i)\\b(?:maksimum|maksymaln|max\\.)\\b', h))
    group_dimension = bool(re.search('(?i)\\b(?:oddział|oddzial|poradnia|komórka|komorka|jednostka|klinika|zakład|zaklad)\\b', h + ' ' + c))
    if has_min and has_max and group_dimension:
        return (True, 'group_min_max_statistics')
    explicit_other_period = re.search('(?i)\\b(?:dane\\s+za|za\\s+miesiąc|za\\s+miesiac|maj|stycze[nń]|luty|marzec|kwiecie[nń]|czerwiec|lipiec|sierpie[nń]|wrzesie[nń]|październik|pazdziernik|listopad|grudzie[nń]).{0,40}\\b(20\\d{2})\\b', c)
    if explicit_other_period and int(explicit_other_period.group(1)) != YEAR:
        return (True, 'wrong_year_or_period')
    stat_terms = sum((bool(re.search(p, h + ' ' + c)) for p in ['(?i)najwyższ', '(?i)najwyzs', '(?i)średni', '(?i)sredni', '(?i)mediana', '(?i)najniższ', '(?i)najnizs']))
    if stat_terms >= 2:
        return (True, 'summary_statistics')
    return (False, '')

def semantic_annual_salary_columns(headers: list[str]) -> tuple[int | None, int | None, int | None]:
    hs = [clean_header(h) for h in headers]
    lp = next((i for i, h in enumerate(hs) if re.search('(?i)^lp\\\\.?$', h)), None)
    amount = next((i for i, h in enumerate(hs) if re.search('(?i)wynagrodzenie.*brutto.*2025|brutto.*2025.*wynagrodzenie', h)), None)
    person = next((i for i, h in enumerate(hs) if re.search('(?i)stanowisko|lekarz|osoba|kod anonimowy|nazwa', h) and i != amount), None)
    return (lp, amount, person)

