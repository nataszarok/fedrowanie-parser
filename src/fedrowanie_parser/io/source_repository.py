"""Read source cases from SQLite."""
from __future__ import annotations

import sqlite3

from ..constants import UNPROCESSED_ATTACHMENT_EXTENSIONS
from ..models import SourceCase

__all__ = [
    "load_source_cases",
]


def load_source_cases(con: sqlite3.Connection) -> list[SourceCase]:
    """Load source cases with institution metadata and concatenated page text."""

    con.row_factory = sqlite3.Row

    query = """
        SELECT
            c.pk AS case_pk,
            TRIM(
                COALESCE(cp.text, '') ||
                CASE
                    WHEN cp.text IS NOT NULL
                         AND at.attachment_text IS NOT NULL
                    THEN CHAR(10)
                    ELSE ''
                END ||
                COALESCE(at.attachment_text, '')
            ) AS text,
            c.institution_pk,
            COALESCE(i.name, c.name, '') AS institution_name
        FROM cases AS c
        LEFT JOIN case_pages AS cp
            ON cp.case_pk = c.pk
        LEFT JOIN institutions AS i
            ON i.pk = c.institution_pk
        LEFT JOIN (
            SELECT
                case_pk,
                GROUP_CONCAT(text, CHAR(10)) AS attachment_text
            FROM attachment_texts
            WHERE text IS NOT NULL
              AND TRIM(text) <> ''
            GROUP BY case_pk
        ) AS at
            ON at.case_pk = c.pk
        WHERE
            (cp.text IS NOT NULL AND TRIM(cp.text) <> '')
            OR at.attachment_text IS NOT NULL
        ORDER BY c.pk
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

    placeholders = ", ".join("?" for _ in UNPROCESSED_ATTACHMENT_EXTENSIONS)
    attachment_query = f"""
        SELECT DISTINCT
            a.case_pk,
            a.filename
        FROM attachments AS a
        WHERE LOWER(COALESCE(a.ext, '')) IN ({placeholders})
          AND NOT EXISTS (
              SELECT 1
              FROM attachment_texts AS at
              WHERE at.case_pk = a.case_pk
                AND at.filename = a.filename
                AND TRIM(COALESCE(at.text, '')) <> ''
          )
        ORDER BY a.case_pk, a.filename
    """

    unprocessed_by_case: dict[int, list[str]] = {}
    for row in con.execute(
        attachment_query,
        UNPROCESSED_ATTACHMENT_EXTENSIONS,
    ):
        unprocessed_by_case.setdefault(row["case_pk"], []).append(row["filename"])

    return [
        SourceCase(
            case_pk=case_pk,
            institution_pk=institution_pk,
            institution_name=institution_name,
            text="\n".join(parts),
            unprocessed_attachments=tuple(unprocessed_by_case.get(case_pk, [])),
        )
        for case_pk, (institution_pk, institution_name, parts) in grouped.items()
    ]
