"""Read source cases from SQLite."""
from __future__ import annotations

import sqlite3

from ..models import SourceCase

__all__ = [
    "load_source_cases",
]


def load_source_cases(con: sqlite3.Connection) -> list[SourceCase]:
    """Load source cases with institution metadata and concatenated page text."""
    con.row_factory = sqlite3.Row
    query = """
        SELECT
            cp.case_pk,
            cp.text,
            c.institution_pk,
            COALESCE(i.name, c.name, '') AS institution_name
        FROM case_pages AS cp
        LEFT JOIN cases AS c
            ON c.pk = cp.case_pk
        LEFT JOIN institutions AS i
            ON i.pk = c.institution_pk
        WHERE cp.text IS NOT NULL
          AND TRIM(cp.text) <> ''
        ORDER BY cp.case_pk, cp.rowid
    """

    grouped: dict[int, tuple[int | None, str, list[str]]] = {}

    for row in con.execute(query):
        case_pk = row["case_pk"]
        if case_pk not in grouped:
            grouped[case_pk] = (
                row["institution_pk"],
                row["institution_name"],
                [],
            )
        grouped[case_pk][2].append(row["text"] or "")

    return [
        SourceCase(
            case_pk=case_pk,
            institution_pk=institution_pk,
            institution_name=institution_name,
            text="\n".join(parts),
        )
        for case_pk, (institution_pk, institution_name, parts) in grouped.items()
    ]
