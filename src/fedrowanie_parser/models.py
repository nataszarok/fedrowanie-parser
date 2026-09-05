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
    specialization: Optional[str]
    contract_type: Optional[str]
    net_compensation: Optional[float]
    gross_compensation: Optional[float]
    page_number: Optional[int]
    parser: str
    confidence: str
    raw_row: str
    comment: Optional[str] = None
    organizational_unit: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_status: Optional[str] = None
    doctor_initials: Optional[str] = None
    recipient_type: str = 'doctor'
    recipient_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.normalize_missing_text()

    def normalize_missing_text(self) -> None:
        """Canonicalize blank optional text fields to ``None``.

        Enrichment mutates ``SalaryRow`` instances after construction, so this
        method is also called at pipeline/storage boundaries to keep the public
        data model consistent.
        """
        for field_name in (
            "specialization", "contract_type", "comment",
            "organizational_unit", "doctor_name", "doctor_status",
            "doctor_initials", "recipient_name",
        ):
            value = getattr(self, field_name)
            if isinstance(value, str) and not value.strip():
                setattr(self, field_name, None)

@dataclass(frozen=True)
class SourceCase:
    """Source case assembled from source text, institution metadata and attachment diagnostics."""

    case_pk: int
    institution_pk: Optional[int]
    institution_name: str
    text: str
    unprocessed_attachments: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaseFlags:
    """Independent procedural signals detected in recipient correspondence."""

    requested_more_time: bool = False
    asked_about_anonymization: bool = False
    requested_clarification: bool = False
    requested_processed_info_justification: bool = False
    fee_notice: bool = False
    transferred_or_not_competent: bool = False
    formal_deficiency_request: bool = False
    refusal_detected: bool = False
    unprocessed_attachment: bool = False


@dataclass(frozen=True)
class CaseParseStatus:
    """Case-level extraction status persisted for diagnostics."""

    case_pk: int
    institution_pk: Optional[int]
    institution_name: str
    status: str
    reason: str
    parsed_candidate_rows: int
    flags: CaseFlags = CaseFlags()


@dataclass
class ExtractionResult:
    """Detailed salary rows plus case-level extraction diagnostics."""

    rows: list[SalaryRow]
    statuses: list[CaseParseStatus]

