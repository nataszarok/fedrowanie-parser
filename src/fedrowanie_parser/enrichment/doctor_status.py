"""Extract physician role and training status independently of specialization."""


from __future__ import annotations

from ..constants import (
    DOCTOR_STATUS_PATTERNS,
    DOCTOR_STATUS_GENERIC_ID_RE,
)
import re

__all__ = [
    "norm",
    "extract_status",
]

def norm(s):
    """Normalize whitespace and punctuation in a text value."""
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

def extract_status(nazwa='',raw_row='',existing_spec=''):
    """Extract physician role or training status from row context."""
    for s in [norm(nazwa),norm(existing_spec),norm(raw_row)]:
        if not s or DOCTOR_STATUS_GENERIC_ID_RE.fullmatch(s): continue
        for pat,label in DOCTOR_STATUS_PATTERNS:
            if pat.search(s):
                return label, bool(norm(existing_spec) and pat.fullmatch(norm(existing_spec)))
    return '',False

