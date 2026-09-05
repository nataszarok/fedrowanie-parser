"""Human review state for generic-ingestion documents."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .storage import init_staging

__all__ = ["list_documents", "set_review_status", "resolve_source_file"]

_REVIEW_STATUSES = {"PENDING", "APPROVED", "REJECTED"}


def list_documents(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return staged documents ordered by source filename."""
    init_staging(con)
    con.row_factory = sqlite3.Row
    return list(
        con.execute(
            """
            SELECT source_file, institution_name, status, reason, accepted_rows,
                   gross_sum, count_match, gross_match, review_status, review_note,
                   reviewed_at, staging_fingerprint
            FROM ingestion_documents
            ORDER BY source_file
            """
        )
    )


def resolve_source_file(con: sqlite3.Connection, selector: str) -> str:
    """Resolve a full path, basename, or unique substring to one staged source file."""
    init_staging(con)
    files = [row[0] for row in con.execute("SELECT source_file FROM ingestion_documents")]
    if selector in files:
        return selector
    basename_matches = [item for item in files if Path(item).name == selector]
    if len(basename_matches) == 1:
        return basename_matches[0]
    folded = selector.casefold()
    substring_matches = [item for item in files if folded in Path(item).name.casefold()]
    if len(substring_matches) == 1:
        return substring_matches[0]
    if not substring_matches and not basename_matches:
        raise ValueError(f"No staged document matches: {selector}")
    matches = basename_matches or substring_matches
    names = ", ".join(Path(item).name for item in matches[:8])
    raise ValueError(f"Ambiguous document selector {selector!r}: {names}")


def set_review_status(
    con: sqlite3.Connection,
    source_file: str,
    status: str,
    note: str = "",
) -> None:
    """Set human review status without modifying extracted salary rows."""
    normalized = status.strip().upper()
    if normalized not in _REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    init_staging(con)
    resolved = resolve_source_file(con, source_file)
    con.execute(
        """
        UPDATE ingestion_documents
        SET review_status = ?, review_note = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE source_file = ?
        """,
        (normalized, note, resolved),
    )
    con.commit()
