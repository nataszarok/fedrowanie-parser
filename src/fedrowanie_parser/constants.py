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
