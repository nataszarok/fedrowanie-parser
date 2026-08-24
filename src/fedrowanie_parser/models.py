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
    komentarz: str = ""
    jednostka_oddzial: str = ""
    imie_nazwisko: str = ""
    stanowisko_status: str = ""
    inicjaly: str = ""


@dataclass(frozen=True)
class SourceCase:
    """Source case assembled from case pages and institution metadata."""

    case_pk: int
    institution_pk: Optional[int]
    institution_name: str
    text: str


@dataclass(frozen=True)
class CaseParseStatus:
    """Case-level extraction status persisted for diagnostics."""

    case_pk: int
    institution_pk: Optional[int]
    institution_name: str
    status: str
    reason: str
    parsed_candidate_rows: int


@dataclass
class ExtractionResult:
    """Detailed salary rows plus case-level extraction diagnostics."""

    rows: list[SalaryRow]
    statuses: list[CaseParseStatus]
