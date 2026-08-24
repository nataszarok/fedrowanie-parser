"""Case-level extraction service.

This module provides a stable semantic boundary around the legacy-compatible
pipeline implementation. It exists so future refactors can move logic out of
`pipeline.py` without changing CLI or storage contracts.
"""
from __future__ import annotations

from typing import Iterable

from ..models import SalaryRow



__all__ = [
    "validate_case_rows",
]

def validate_case_rows(rows: Iterable[SalaryRow]) -> list[SalaryRow]:
    """Materialize case rows and validate required identifiers."""
    materialized = list(rows)
    for row in materialized:
        if row.case_pk is None or row.institution_pk is None:
            raise ValueError("SalaryRow requires case_pk and institution_pk.")
    return materialized

