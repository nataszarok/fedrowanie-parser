from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class CellTable:
    source_file: Path
    sheet: str
    page: int | None
    rows: list[list[Any]]
    extractor: str

@dataclass
class IngestedSalary:
    source_file: str
    source_locator: str
    institution_name: str
    institution_pk: int | None
    source_name: str
    doctor_name: str = ""
    recipient_type: str = "anonymous_doctor"
    contract_type: str = ""
    specialization: str = ""
    net_compensation: float | None = None
    gross_compensation: float | None = None
    raw_row: str = ""
    parser: str = "generic-ingestion"
    confidence: str = "średnia"
    comment: str = ""

@dataclass
class DocumentIngestion:
    source_file: str
    format: str
    institution_name: str
    institution_pk: int | None
    status: str
    reason: str
    tables_seen: int = 0
    candidate_rows: int = 0
    accepted_rows: int = 0
    gross_sum: float = 0.0
    net_sum: float = 0.0
    rows: list[IngestedSalary] = field(default_factory=list)
    source_counts: list[int] = field(default_factory=list)
    source_gross_sums: list[float] = field(default_factory=list)
    count_match: bool | None = None
    gross_match: bool | None = None
