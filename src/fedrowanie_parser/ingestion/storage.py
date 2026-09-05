"""SQLite storage for generic-ingestion staging and review metadata."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .models import DocumentIngestion

__all__ = ["init_staging", "replace_document", "staging_fingerprint"]


def init_staging(con: sqlite3.Connection) -> None:
    """Create or migrate staging, review, and promotion bookkeeping tables."""
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS ingestion_documents (
            source_file TEXT PRIMARY KEY,
            format TEXT,
            institution_name TEXT,
            institution_pk INTEGER,
            status TEXT,
            reason TEXT,
            tables_seen INTEGER,
            candidate_rows INTEGER,
            accepted_rows INTEGER,
            gross_sum REAL,
            net_sum REAL,
            source_counts TEXT,
            source_gross_sums TEXT,
            count_match INTEGER,
            gross_match INTEGER,
            review_status TEXT DEFAULT 'PENDING',
            review_note TEXT DEFAULT '',
            reviewed_at TEXT,
            staging_fingerprint TEXT,
            promoted_at TEXT,
            promotion_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS ingestion_rows (
            source_file TEXT,
            source_locator TEXT,
            institution_name TEXT,
            institution_pk INTEGER,
            source_name TEXT,
            doctor_name TEXT,
            doctor_initials TEXT,
            recipient_type TEXT,
            contract_type TEXT,
            specialization TEXT,
            net_compensation REAL,
            gross_compensation REAL,
            raw_row TEXT,
            parser TEXT,
            confidence TEXT,
            comment TEXT
        );

        CREATE TABLE IF NOT EXISTS ingestion_promotions (
            promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            staging_fingerprint TEXT NOT NULL,
            institution_name TEXT,
            status TEXT NOT NULL,
            expected_count INTEGER NOT NULL,
            expected_gross REAL NOT NULL,
            actual_count INTEGER,
            actual_gross REAL,
            promoted_at TEXT,
            rolled_back_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ingestion_rows_source_file
            ON ingestion_rows(source_file);
        CREATE INDEX IF NOT EXISTS idx_ingestion_promotions_source_file
            ON ingestion_promotions(source_file, status);
        """
    )
    _ensure_columns(
        con,
        "ingestion_documents",
        {
            "source_counts": "TEXT",
            "source_gross_sums": "TEXT",
            "count_match": "INTEGER",
            "gross_match": "INTEGER",
            "review_status": "TEXT DEFAULT 'PENDING'",
            "review_note": "TEXT DEFAULT ''",
            "reviewed_at": "TEXT",
            "staging_fingerprint": "TEXT",
            "promoted_at": "TEXT",
            "promotion_id": "INTEGER",
        },
    )
    _ensure_columns(con, "ingestion_rows", {"doctor_initials": "TEXT"})
    for column in (
        "doctor_name", "doctor_initials", "contract_type",
        "specialization", "comment",
    ):
        con.execute(
            f"UPDATE ingestion_rows SET {column}=NULL "
            f"WHERE {column} IS NOT NULL AND TRIM({column})=''"
        )
    con.execute(
        "UPDATE ingestion_documents SET review_status='PENDING' WHERE review_status IS NULL OR review_status=''"
    )
    con.commit()


def _ensure_columns(
    con: sqlite3.Connection,
    table: str,
    columns: dict[str, str],
) -> None:
    existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    for name, type_sql in columns.items():
        if name not in existing:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {type_sql}")


def staging_fingerprint(document: DocumentIngestion) -> str:
    """Return a deterministic hash of semantic staging output for one document."""
    payload = [
        {
            "source_locator": row.source_locator,
            "institution_pk": row.institution_pk,
            "institution_name": row.institution_name,
            "source_name": row.source_name,
            "doctor_name": row.doctor_name,
            "doctor_initials": row.doctor_initials,
            "recipient_type": row.recipient_type,
            "contract_type": row.contract_type,
            "specialization": row.specialization,
            "net_compensation": row.net_compensation,
            "gross_compensation": row.gross_compensation,
            "raw_row": row.raw_row,
            "parser": row.parser,
            "confidence": row.confidence,
            "comment": row.comment,
        }
        for row in document.rows
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def replace_document(con: sqlite3.Connection, document: DocumentIngestion) -> None:
    """Replace one staged document while preserving review only if output is unchanged."""
    init_staging(con)
    new_fingerprint = staging_fingerprint(document)
    old = con.execute(
        """
        SELECT staging_fingerprint, review_status, review_note, reviewed_at,
               promoted_at, promotion_id
        FROM ingestion_documents
        WHERE source_file = ?
        """,
        (document.source_file,),
    ).fetchone()
    unchanged = bool(old and old[0] == new_fingerprint)
    review_status = old[1] if unchanged and old[1] else "PENDING"
    review_note = old[2] if unchanged and old[2] else ""
    reviewed_at = old[3] if unchanged else None
    promoted_at = old[4] if unchanged else None
    promotion_id = old[5] if unchanged else None

    con.execute("DELETE FROM ingestion_rows WHERE source_file = ?", (document.source_file,))
    con.execute("DELETE FROM ingestion_documents WHERE source_file = ?", (document.source_file,))
    con.execute(
        """
        INSERT INTO ingestion_documents (
            source_file, format, institution_name, institution_pk, status, reason,
            tables_seen, candidate_rows, accepted_rows, gross_sum, net_sum,
            source_counts, source_gross_sums, count_match, gross_match,
            review_status, review_note, reviewed_at, staging_fingerprint,
            promoted_at, promotion_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document.source_file,
            document.format,
            document.institution_name,
            document.institution_pk,
            document.status,
            document.reason,
            document.tables_seen,
            document.candidate_rows,
            document.accepted_rows,
            document.gross_sum,
            document.net_sum,
            json.dumps(document.source_counts),
            json.dumps(document.source_gross_sums),
            None if document.count_match is None else int(document.count_match),
            None if document.gross_match is None else int(document.gross_match),
            review_status,
            review_note,
            reviewed_at,
            new_fingerprint,
            promoted_at,
            promotion_id,
        ),
    )
    con.executemany(
        """
        INSERT INTO ingestion_rows (
            source_file, source_locator, institution_name, institution_pk,
            source_name, doctor_name, doctor_initials, recipient_type, contract_type,
            specialization, net_compensation, gross_compensation, raw_row,
            parser, confidence, comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.source_file,
                row.source_locator,
                row.institution_name,
                row.institution_pk,
                row.source_name,
                row.doctor_name or None,
                row.doctor_initials or None,
                row.recipient_type,
                row.contract_type or None,
                row.specialization or None,
                row.net_compensation,
                row.gross_compensation,
                row.raw_row,
                row.parser,
                row.confidence,
                row.comment or None,
            )
            for row in document.rows
        ],
    )
    con.commit()
