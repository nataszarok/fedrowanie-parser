"""Project-wide constants and compiled regular expressions.

Keep configuration-like values, parser thresholds, canonical vocabularies and
compiled regexes here. Runtime state and function-local tuning values should
remain close to the code that uses them.
"""
from __future__ import annotations

import re

YEAR = 2025

PAGE_RE = re.compile('-+\\s*początek strony\\s+(\\d+)\\s*-+\\s*(.*?)(?=-+\\s*koniec strony\\s+\\1\\s*-+|\\Z)', re.I | re.S)

MONEY_TOKEN = re.compile('(?<![\\d.])(?:\\d{1,3}(?:[ \\u00a0]\\d{3})+|\\d{1,3}(?:\\.\\d{3})+|\\d{1,7})(?:[,.]\\d{1,2})?(?:\\s*zł)?(?![\\d])', re.I)

DATE_RE = re.compile('\\b(?:0?[1-9]|[12]\\d|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:19|20)\\d{2}\\b')

ISO_DATE_RE = re.compile('\\b(?:19|20)\\d{2}-\\d{2}-\\d{2}\\b')

PHONEISH_RE = re.compile('(?i)\\b(?:tel\\.?|fax|nip|regon|krs|sygn\\.?|znak|nr\\s+pisma|e-mail|email)\\b')

SUMMARY_RE = re.compile('(?i)\\b(?:razem|suma|sumaryczn|ogółem|łącznie\\s+(?:wszyscy|wszystkich|wynagrodze[nń])|średni[ae]|średnia|mediana|minimum|maksimum|wartość\\s+łączna|podsumowanie|ogólna\\s+kwota)\\b')

PERSON_TOTAL_RE = re.compile('(?i)\\b(?:łączne|roczne|całkowite)\\s+wynagrodzenie\\s+(?:lekarza|lp\\.?\\s*\\d+|nr\\s*\\d+)')

YEAR_OTHER_RE = re.compile('\\b(20\\d{2})\\b')

CONTRACT_PATTERNS = [(re.compile('(?i)umow[ayę]\\s+o\\s+prac[ęe]|etat|stosunek\\s+pracy'), 'umowa o pracę'), (re.compile('(?i)umow[ayę]\\s+zlecen|zlecenie'), 'umowa zlecenia'), (re.compile('(?i)kontrakt|cywilno[- ]?prawn|działalnoś[ćc]\\s+gospodar'), 'kontrakt/cywilnoprawna'), (re.compile('(?i)umow[ayę]\\s+o\\s+dzieło|dzieło'), 'umowa o dzieło')]

NET_RE = re.compile('(?i)\\bnetto\\b')

GROSS_RE = re.compile('(?i)\\bbrutto\\b')

SPECIALIZATION_WORDS = re.compile('(?i)\\b(?:chirurg|ginekolog|położ|internist|pediatr|okulist|neurolog|psychiatr|kardiolog|anestez|ortoped|urolog|radiolog|onkolog|laryng|otolaryng|dermatolog|nefrolog|hematolog|endokrynolog|gastrolog|pulmonolog|reumatolog|medycyn|rezydent|asystent|ordynator|kierownik|lekarz)\\b')

MONTH_NAME_RE = '(?:stycze[nń]|luty|marzec|kwiecie[nń]|maj|czerwiec|lipiec|sierpie[nń]|wrzesie[nń]|październik|pazdziernik|listopad|grudzie[nń])'

THREAD_DATE_RE = re.compile('^\\d{1,2}\\s+(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)\\s+20\\d{2}\\s+\\d{1,2}:\\d{2}$', re.I)

AUTO_REPLY_RE = re.compile('(?i)Kategoryzacja AI została pominięta dla listu z automatyczną odpowiedzią|To jest potwierdzenie dostarczenia|automatyczn[aey]\\s+odpowied|potwierdzenie otrzymania')

REQUESTER_SENDER_RE = re.compile('(?i)^(?:SOWP|Sieć Obywatelska Watchdog Polska|Siec Obywatelska Watchdog Polska)$')

QUOTE_CUT_PATTERNS = [re.compile('(?m)^W dniu .+ napisał\\(a\\):\\s*$', re.I), re.compile('(?m)^-{2,}\\s*Original Message\\s*-{2,}\\s*$', re.I), re.compile('(?m)^From:\\s+.+$', re.I), re.compile('(?m)^Od:\\s+.+$', re.I)]

PARSER_RANK = {'ocr-broken-numbered-table': 11, 'parallel-name-amount-lists': 10, 'vertical-idx-code-gross-net': 9, 'parallel-index-amount': 9, 'anon-lekarz-inline-list': 9, 'indexed-single-salary-md': 8, 'indexed-total-gross-continuation': 9, 'salary-bracket-index': 10, 'embedded-numbered-salary-list': 10, 'numbered-amount-only-series': 10, 'specialty-amount-lines': 10, 'vertical-role-named-amount': 10, 'vertical-named-salary-table': 10, 'two-section-vertical': 10, 'explicit-annual-prose-salary': 10, 'vertical-index-code-label-amount': 9, 'numbered-named-inline': 9,
    'body-lekarz-number-amount': 10,
    'body-lp-amount': 10,
    'parallel-doctor-amount-lists': 10,
    'anonymous-amount-only-series': 10, 'annual-amount-contract-lines': 10, 'contract-practice-cost-list': 10, 'forma-name-amount-ocr': 9, 'single-anonymized-annual-amount': 10, 'lekarz-inline-specialty': 9, 'markdown-section-state': 6, 'markdown-net-gross': 5, 'markdown-multi-contract': 5, 'markdown-table': 4, 'markdown-paid-2025': 4, 'markdown-empty-lp': 4, 'markdown-continuation': 4, 'markdown-3col-continuation': 4, 'vertical-label-amount': 5, 'vertical-index-name-amount': 6, 'ocr-contract-amount-list': 5, 'plain-inline': 3, 'plain-index-amount': 2, 'plain-vertical': 1}

STRUCTURED_METADATA_PARSERS = {'contract-practice-cost-list', 'indexed-single-salary-md', 'indexed-total-gross-continuation', 'salary-bracket-index', 'numbered-named-inline', 'anon-lekarz-inline-list'}

TOPN_WORD_RE = re.compile(r'(?i)\b(?:najwy[żz]szych|najwy[żz]sze|najwy[żz]szym)\b')

# Module-specific parser constants

# special_cases/section_salary_list.py
SECTION_SALARY_UNIT_PREFIX_RE=re.compile(
    r'(?i)^(?:oddzia[łl]|pododdzia[łl]|klinika|pracownia|poradni\w*|'
    r'SOR\b|izba przyj[ęe][ćc]|zak[łl]ad|o[śs]rodek)\b'
)

# special_cases/section_salary_list.py
SECTION_SALARY_ITEM_START_RE=re.compile(
    r'(?i)^\s*(?P<idx>\d+|[lI])\.\s*(?P<role>lekarz[^—\-|]*?|'
    r'lek\.?[^—\-|]*?|specjalista[^—\-|]*?|asystent[^—\-|]*?|rezydent[^—\-|]*?)\s*'
    r'(?:—|-)\s*(?P<amount>.+?)\s*$'
)

# special_cases/multi_contract_columns.py
MULTI_CONTRACT_MONEY_RE=re.compile(r'-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})|-?\d{4,9}(?:[,.]\d{2})')

# special_cases/monthly_ledger.py
MONTHLY_LEDGER_ROW_RE = re.compile(
    r"\|\s*(\d{2}\.\d{2}\.(\d{4}))\s*\|\s*([^|]*)\|\s*"
    r"(-?\d{1,3}(?:[ .]\d{3})*(?:,\d{2})|-?\d+,\d{2})\s*\|"
)

# special_cases/monthly_ledger.py
MONTHLY_LEDGER_HEADER_RE = re.compile(
    r"(?is)\|\s*Data\s+Dokumentu\s*\|\s*Podmiot\s*\|\s*Warto(?:s|ś)c\s*\|"
)

# special_cases/monthly_ledger.py
MONTHLY_LEDGER_PROF_PREFIX_RE = re.compile(
    r"(?i)^(?:(?:lek(?:arz)?|dr|prof|mgr)\.?\s*(?:med\.?)?\s+)"
)

# special_cases/monthly_ledger.py
MONTHLY_LEDGER_BUSINESS_RE = re.compile(
    r"(?i)\b(?:sp\.?\s*z\.?\s*o\.?\s*o\.?|spółka|spolka|s\.?c\.?|"
    r"praktyka|gabinet|fizjoterapia|rehabilitacja|kingmed|medyczn\w*|"
    r"nzoz|zoz|poradnia|centrum)\b"
)

# enrichment/attachment_contract.py
ATTACHMENT_CONTRACT_ATTACHMENT_RE = re.compile(
    r'(?im)^(?P<name>[^\n]{1,260}\.(?:pdf|xlsx?|xlsm|ods|csv|docx?|rtf|zip|rar|7z))\s*$'
)

# enrichment/attachment_contract.py
ATTACHMENT_CONTRACT_PATTERNS = [
    ("umowa o pracę", re.compile(
        r'(?i)(?:(?:^|[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])uop(?:[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]|$)|'
        r'um[oó]w\w*[\s._-]+o[\s._-]+prac[ęe])')),
    ("umowa zlecenia", re.compile(r'(?i)um[oó]w\w*[\s._-]+zlecen\w*')),
    ("kontrakt/cywilnoprawna", re.compile(
        r'(?i)(?:kontrakt\w*|um[oó]w\w*[\s._-]+cywiln\w*[- _]?prawn\w*|'
        r'cywiln\w*[- _]?prawn\w*|podwykonawst\w*[\s._-]+medyczn\w*)')),
    ("działalność gospodarcza", re.compile(
        r'(?i)dzia[łl]alno[śs][ćc][\s._-]+gospodarcz\w*')),
]

# enrichment/doctor_initials.py
DOCTOR_INITIALS_MONEY_RE=re.compile(r'^\s*-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})\s*(?:z[łl]|PLN)?\s*$',re.I)

# enrichment/doctor_initials.py
DOCTOR_INITIALS_HEADER_RE=re.compile(r'(?i)^(?:inicja[łl]y|identyfikator\s+lekarza)$')

# enrichment/doctor_initials.py
DOCTOR_INITIALS_SURNAME_HEADER_RE=re.compile(r'(?i)^nazwisko$')

# enrichment/doctor_initials.py
DOCTOR_INITIALS_FIRST_HEADER_RE=re.compile(r'(?i)^imi[ęe]$')

# enrichment/contract_semantic.py
CONTRACT_SEMANTIC_PRACTICE_RE=re.compile(
    r'(?i)\b(?:indywidualna|prywatna|specjalistyczna)?\s*'
    r'(?:specjalistyczna\s+)?praktyka\s+lekarska\b'
)

# enrichment/unit_column.py
UNIT_COLUMN_HEADER_RE = re.compile(
    r'(?i)^(?:'
    r'nazwa\s+kom[oó]rki\s+organizacyjnej|'
    r'kom[oó]rka\s+organizacyjna|'
    r'oddzia[łl](?:/o[śs]rodek/poradnia)?|'
    r'klinika|poradnia|pracownia|o[śs]rodek|'
    r'jednostka(?:\s+organizacyjna)?|'
    r'miejsce\s+udzielania\s+[śs]wiadcze[ńn]|'
    r'miejsce\s+zatrudnienia'
    r')$'
)

# enrichment/unit_column.py
UNIT_COLUMN_HEADER_LIKE_RE = re.compile(
    r'(?i)\b(?:lp\.?|l\.p\.?|nazwisko|imi[ęe]|wynagrodzeni\w*|kwota|'
    r'forma zatrudn\w*|rodzaj umowy|etat|stanowisko|uwagi|okres)\b'
)

# enrichment/unit_column.py
UNIT_COLUMN_MONEY_RE = re.compile(r'-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})|-?\d{4,9}(?:[,.]\d{2})')

# enrichment/unit_column.py
UNIT_COLUMN_SECTION_HEADING_RE = re.compile(
    r'(?i)^(?P<unit>'
    r'(?:oddzia[łl]|pododdzia[łl]|klinika|pracownia|poradnia|'
    r'szpitalny oddzia[łl] ratunkowy|SOR|izba przyj[ęe][ćc]|'
    r'zak[łl]ad|o[śs]rodek)'
    r'[^:\n]{0,170}'
    r'):\s*$'
)

# enrichment/unit_column.py
UNIT_COLUMN_SALARY_ITEM_RE = re.compile(
    r'(?i)^\s*\d+\.\s*(?:lekarz|lek\.?|dr\b|specjalista|asystent|rezydent)'
)

# enrichment/organizational_unit.py
ORGANIZATIONAL_UNIT_RE = re.compile(
    r'(?i)\b(?:pododdzia[łl]|oddzia[łl]|klinika|pracownia|poradnia|'
    r'szpitalny oddzia[łl] ratunkowy|SOR\b|izba przyj[ęe][ćc]|'
    r'nocna i [śs]wi[ąa]teczna opieka(?: zdrowotna| medyczna)?|'
    r'o[śs]rodek rehabilitacji|zak[łl]ad\b|\bkl\.\s*|^o\.\s*)'
)

# enrichment/organizational_unit.py
ORGANIZATIONAL_CONTACT_RE = re.compile(r'(?i)\b(?:tel\.?|fax|e-?mail|www\.|ul\.|telefon)\b')

# enrichment/organizational_unit.py
ORGANIZATIONAL_MONEY_RE = re.compile(r'\d{1,3}(?:[ .]\d{3})*[,.]\d{2}')

# enrichment/organizational_unit.py
ORGANIZATIONAL_ROLE_RE = re.compile(r'(?i)^(?:koordynator|zast[ęe]pca koordynatora|z-ca koordynatora|'
                     r'ordynator|zast[ęe]pca ordynatora|kierownik|p\.?o\.?.*)$')

# enrichment/person_name.py
PERSON_NAME_HEADER_RE=re.compile(r'(?i)^(?:nazwisko\s+i\s+imi[ęe]|nazwisko\s+imi[ęe]|imi[ęe]\s+i\s+nazwisko|imi[ęe]\s+nazwisko|nazwisko(?:\s+lekarza)?|dane\s+lekarza)$')

# enrichment/person_name.py
PERSON_NAME_MONEY_RE=re.compile(r'-?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d{2})|-?\d{4,9}(?:[,.]\d{2})')

# enrichment/person_name.py
PERSON_NAME_BAD_RE=re.compile(r'(?i)\b(?:lekarz|specjalista|specjalizacja|asystent|rezydent|ordynator|koordynator|kierownik|zast[ęe]pca|oddzia[łl]|klinika|poradnia|pracownia|zak[łl]ad|o[śs]rodek|chirurg|ginekolog|pediatr|psychiatr|radiolog|kardiolog|neurolog|nefrolog|urolog|onkolog|anestez|medycyn|umowa|kontrakt|etat|wynagrodzenie|kwota|brutto|netto)\b')

# enrichment/person_name.py
PERSON_NAME_TOKEN_RE=re.compile(r"^[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźżÀ-ÖØ-öø-ÿ'’-]+$")

# enrichment/specialization.py
SPECIALIZATION_PATTERNS = [
    ("radiologia i diagnostyka obrazowa", re.compile(r'(?i)\bradiologia\s+i\s+diagnostyka\s+obrazowa\b')),
    ("radiologia", re.compile(r'(?i)\bradiolog(?:ia|ii|icz\w*|a|iem)?\b|\bradiodiagnost\w*\b')),
    ("psychiatria dzieci i młodzieży", re.compile(r'(?i)\bpsychiatri\w+\s+dzieci\s+i\s+m[łl]odzie[żz]y\b')),
    ("psychiatria", re.compile(r'(?i)\bpsychiatr\w*\b')),
    ("anestezjologia i intensywna terapia", re.compile(r'(?i)\banestezjolog\w*(?:\s+i\s+intensywn\w+\s+terapi\w*)?\b')),
    ("neurochirurgia", re.compile(r'(?i)\bneurochirurg\w*\b')),
    ("hematologia", re.compile(r'(?i)\bhematolog\w*\b')),
    ("chirurgia klatki piersiowej", re.compile(r'(?i)\bchirurg\w+\s+klatki\s+piersiow\w*\b')),
    ("chirurgia naczyniowa", re.compile(r'(?i)\bchirurg\w+\s+naczyniow\w*\b')),
    ("chirurgia ogólna", re.compile(r'(?i)\bchirurg\w+\s+og[oó]ln\w*\b')),
    ("chirurgia", re.compile(r'(?i)\bchirurg\w*\b')),
    ("kardiochirurgia", re.compile(r'(?i)\bkardiochirurg\w*\b')),
    ("kardiologia", re.compile(r'(?i)\bkardiolog\w*\b')),
    ("nefrologia", re.compile(r'(?i)\bnefrolog\w*\b')),
    ("neurologia", re.compile(r'(?i)\bneurolog\w*\b')),
    ("urologia", re.compile(r'(?i)\burolog\w*\b')),
    ("okulistyka", re.compile(r'(?i)\bokulist\w*\b')),
    ("otolaryngologia", re.compile(r'(?i)\botolaryngolog\w*|\blaryngolog\w*\b')),
    ("pediatria", re.compile(r'(?i)\bpediatr\w*\b')),
    ("ginekologia i położnictwo", re.compile(r'(?i)\b(?:ginekolog\w*.{0,20}po[łl]o[żz]nictw\w*|po[łl]o[żz]nictw\w*.{0,20}ginekolog\w*)\b')),
    ("ginekologia", re.compile(r'(?i)\bginekolog\w*\b')),
    ("choroby wewnętrzne", re.compile(r'(?i)\bchor[oó]b\w+\s+wewn[ęe]trzn\w*|\binternist\w*\b')),
    ("medycyna rodzinna", re.compile(r'(?i)\bmedycyn\w+\s+rodzinn\w*\b')),
    ("rehabilitacja medyczna", re.compile(r'(?i)\brehabilitacj\w+\s+medyczn\w*\b')),
    ("rehabilitacja", re.compile(r'(?i)\brehabilitacj\w*\b')),
    ("medycyna ratunkowa", re.compile(r'(?i)\bmedycyn\w+\s+ratunkow\w*\b')),
    ("onkologia kliniczna", re.compile(r'(?i)\bonkolog\w+\s+kliniczn\w*\b')),
    ("onkologia", re.compile(r'(?i)\bonkolog\w*\b')),
    ("pulmonologia", re.compile(r'(?i)\bpulmonolog\w*\b|\bchor[oó]b\w+\s+p[łl]uc\b')),
    ("dermatologia", re.compile(r'(?i)\bdermatolog\w*\b')),
    ("endokrynologia", re.compile(r'(?i)\bendokrynolog\w*\b')),
    ("ortopedia i traumatologia", re.compile(r'(?i)\bortoped\w*.{0,30}traumatolog\w*|\btraumatolog\w*.{0,30}ortoped\w*')),
    ("ortopedia", re.compile(r'(?i)\bortoped\w*\b')),
    ("medycyna paliatywna", re.compile(r'(?i)\bmedycyn\w+\s+paliatywn\w*\b')),
]

# enrichment/specialization.py
SPECIALIZATION_GENERIC_ONLY_RE = re.compile(
    r'(?i)^(?:lekarz\s+)?(?:specjalista|lekarz specjalista|'
    r'lekarz w trakcie specjalizacji|lekarz bez specjalizacji)$'
)

# enrichment/doctor_status.py
DOCTOR_STATUS_PATTERNS=[
(re.compile(r'(?i)\blekarz\s+w\s+trakcie\s+specjalizacji\b'),'lekarz w trakcie specjalizacji'),
(re.compile(r'(?i)\blekarz\s+bez\s+specjalizacji\b'),'lekarz bez specjalizacji'),
(re.compile(r'(?i)\blekarz\s+specjalista\b'),'lekarz specjalista'),
(re.compile(r'(?i)\bstarszy\s+asystent\b'),'starszy asystent'),
(re.compile(r'(?i)\blekarz\s+asystent(?:\s+oddzia[łl]u)?\b'),'lekarz asystent'),
(re.compile(r'(?i)\basystent(?:\s+oddzia[łl]u)?\b'),'asystent'),
(re.compile(r'(?i)\brezydent\b'),'rezydent'),
(re.compile(r'(?i)\bordynator\b'),'ordynator'),
(re.compile(r'(?i)\bkoordynator\b'),'koordynator'),
(re.compile(r'(?i)\bkierownik(?:\s+oddzia[łl]u)?\b'),'kierownik'),
(re.compile(r'(?i)\bz(?:ast[ęe]pca|-ca)\s+(?:ordynatora|koordynatora|kierownika)\b'),'zastępca kierownika/koordynatora'),
]

# enrichment/doctor_status.py
DOCTOR_STATUS_GENERIC_ID_RE=re.compile(r'(?i)^lekarz\s+\d+$')

__all__ = [
    "YEAR",
    "PAGE_RE",
    "MONEY_TOKEN",
    "DATE_RE",
    "ISO_DATE_RE",
    "PHONEISH_RE",
    "SUMMARY_RE",
    "PERSON_TOTAL_RE",
    "YEAR_OTHER_RE",
    "CONTRACT_PATTERNS",
    "NET_RE",
    "GROSS_RE",
    "SPECIALIZATION_WORDS",
    "MONTH_NAME_RE",
    "THREAD_DATE_RE",
    "AUTO_REPLY_RE",
    "REQUESTER_SENDER_RE",
    "QUOTE_CUT_PATTERNS",
    "PARSER_RANK",
    "STRUCTURED_METADATA_PARSERS",
    "TOPN_WORD_RE",
    "SECTION_SALARY_UNIT_PREFIX_RE",
    "SECTION_SALARY_ITEM_START_RE",
    "MULTI_CONTRACT_MONEY_RE",
    "MONTHLY_LEDGER_ROW_RE",
    "MONTHLY_LEDGER_HEADER_RE",
    "MONTHLY_LEDGER_PROF_PREFIX_RE",
    "MONTHLY_LEDGER_BUSINESS_RE",
    "ATTACHMENT_CONTRACT_ATTACHMENT_RE",
    "ATTACHMENT_CONTRACT_PATTERNS",
    "DOCTOR_INITIALS_MONEY_RE",
    "DOCTOR_INITIALS_HEADER_RE",
    "DOCTOR_INITIALS_SURNAME_HEADER_RE",
    "DOCTOR_INITIALS_FIRST_HEADER_RE",
    "CONTRACT_SEMANTIC_PRACTICE_RE",
    "UNIT_COLUMN_HEADER_RE",
    "UNIT_COLUMN_HEADER_LIKE_RE",
    "UNIT_COLUMN_MONEY_RE",
    "UNIT_COLUMN_SECTION_HEADING_RE",
    "UNIT_COLUMN_SALARY_ITEM_RE",
    "ORGANIZATIONAL_UNIT_RE",
    "ORGANIZATIONAL_CONTACT_RE",
    "ORGANIZATIONAL_MONEY_RE",
    "ORGANIZATIONAL_ROLE_RE",
    "PERSON_NAME_HEADER_RE",
    "PERSON_NAME_MONEY_RE",
    "PERSON_NAME_BAD_RE",
    "PERSON_NAME_TOKEN_RE",
    "SPECIALIZATION_PATTERNS",
    "SPECIALIZATION_GENERIC_ONLY_RE",
    "DOCTOR_STATUS_PATTERNS",
    "DOCTOR_STATUS_GENERIC_ID_RE",
]
