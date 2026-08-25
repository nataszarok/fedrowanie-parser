"""Core output data models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class SalaryRow:
    """Normalized physician compensation record produced by the parser."""

    case_pk: int
    institution_pk: Optional[int]
    institution_name: str
    source_name: str
    specialization: str
    contract_type: str
    net_compensation: Optional[float]
    gross_compensation: Optional[float]
    page_number: Optional[int]
    parser: str
    confidence: str
    raw_row: str
    comment: str = ''
    organizational_unit: str = ''
    doctor_name: str = ''
    doctor_status: str = ''
    doctor_initials: str = ''

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

