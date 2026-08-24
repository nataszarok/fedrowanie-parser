
from __future__ import annotations
import re
def norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')
P=[
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
GEN=re.compile(r'(?i)^lekarz\s+\d+$')
def extract_status(nazwa='',raw_row='',existing_spec=''):
    for s in [norm(nazwa),norm(existing_spec),norm(raw_row)]:
        if not s or GEN.fullmatch(s): continue
        for pat,label in P:
            if pat.search(s):
                return label, bool(norm(existing_spec) and pat.fullmatch(norm(existing_spec)))
    return '',False
