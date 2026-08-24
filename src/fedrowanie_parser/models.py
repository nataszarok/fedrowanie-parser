"""Core output data models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class SalaryRow:
    case_pk: int
    institution_pk: Optional[int]
    placowka: str
    nazwa: str
    specjalizacja: str
    typ_umowy: str
    netto: Optional[float]
    brutto: Optional[float]
    strona: Optional[int]
    parser: str
    pewnosc: str
    raw_row: str
    komentarz: str = ''
    jednostka_oddzial: str = ''
    imie_nazwisko: str = ''
    stanowisko_status: str = ''
    inicjaly: str = ''

