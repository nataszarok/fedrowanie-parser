
from __future__ import annotations
import re

def _norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip()

PRACTICE_RE=re.compile(
    r'(?i)\b(?:indywidualna|prywatna|specjalistyczna)?\s*'
    r'(?:specjalistyczna\s+)?praktyka\s+lekarska\b'
)

def infer_contract_from_record_and_section(doc:str, raw_row:str):
    """
    Conservative semantic recovery for missing contract type.
    Returns (type, evidence) or None.

    Rules intentionally require either evidence in the record itself or a
    strong section/list introducer immediately governing the record.
    """
    raw=_norm(raw_row)
    if PRACTICE_RE.search(raw):
        return ('kontrakt/cywilnoprawna','praktyka lekarska w rekordzie')

    text=str(doc or '')
    p=text.find(str(raw_row or ''))
    if p<0:
        return None
    before=_norm(text[max(0,p-2200):p])
    tail=before[-1800:]

    # Explicit "form of employment" label governing the following list.
    m=list(re.finditer(r'(?i)forma\s+zatrudnienia\s*:\s*(kontrakt\w*|umow\w*\s+o\s+prac[ęe]|umow\w*\s+zlecen\w*)',tail))
    if m:
        v=m[-1].group(1).casefold()
        if 'kontr' in v: return ('kontrakt/cywilnoprawna','Forma zatrudnienia: kontrakt')
        if 'prac' in v: return ('umowa o pracę','Forma zatrudnienia: umowa o pracę')
        if 'zlecen' in v: return ('umowa zlecenia','Forma zatrudnienia: umowa zlecenia')

    # Strong table/section labels immediately before a table/list.
    if re.search(r'(?is)(?:^|\|)\s*umow\w*\s+o\s+prac[ęe]\s*(?:\||$).{0,500}(?:\blp\b|pracownik|lekarz)',tail):
        return ('umowa o pracę','nagłówek sekcji/tabeli: umowa o pracę')
    if re.search(r'(?is)wynagrodzenia\s+(?:lekarzy\s+)?zleceniobiorc\w*.{0,120}umow\w*\s+zlecen',tail):
        return ('umowa zlecenia','sekcja zleceniobiorców na umowie zlecenia')
    if re.search(r'(?is)wynagrodzenia\s+lekarzy\s+zatrudnionych.{0,100}(?:stosunku\s+pracy|umow\w*\s+o\s+prac)',tail):
        return ('umowa o pracę','sekcja lekarzy zatrudnionych w stosunku pracy')

    # Medical-services contracts under art. 26/27: "przyjmujący zamówienie".
    if re.search(r'(?is)przyjmuj\w+\s+zam[oó]wieni\w*.{0,250}umow\w*.{0,250}'
                 r'udzielani\w+\s+[śs]wiadcze[ńn]\s+zdrowotn\w*.{0,250}'
                 r'art\.?\s*26.{0,80}art\.?\s*27',tail):
        return ('kontrakt/cywilnoprawna','przyjmujący zamówienie; świadczenia zdrowotne art. 26/27')

    # A whole following list explicitly described as civil-law medical services.
    if re.search(r'(?is)ma\s+zawarte\s+umow\w+\s+cywilno\s*[-–—]?\s*prawn\w+.{0,500}'
                 r'wyp[łl]aci[łl].{0,250}wynagrodzeni\w+\s+nast[ęe]puj[ąa]cym\s+lekarz',tail):
        return ('kontrakt/cywilnoprawna','lista lekarzy objętych umowami cywilnoprawnymi')

    # Competition-based medical-service agreements followed by a list of businesses.
    if re.search(r'(?is)[śs]wiadczeni\w+\s+zdrowotn\w+.{0,180}na\s+podstawie\s+um[oó]w'
                 r'.{0,300}post[ęe]powani\w+\s+konkursow\w+.{0,350}'
                 r'list[ęa]\s+podmiot\w+',tail):
        return ('kontrakt/cywilnoprawna','świadczenia zdrowotne po postępowaniu konkursowym')

    return None
