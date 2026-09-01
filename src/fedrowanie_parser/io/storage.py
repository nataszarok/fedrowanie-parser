"""Persist parser outputs to SQLite and CSV."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from ..models import CaseParseStatus, SalaryRow

__all__ = [
    "write_cases_status",
    "write_extracted_rows",
    "write_summary",
    "write_cases_status_csv",
    "write_extracted_csv",
    "write_summary_csv",
]


def write_cases_status(
    con: sqlite3.Connection,
    statuses: list[CaseParseStatus],
) -> None:
    """Replace the case-level parser diagnostics table."""
    con.execute("DROP TABLE IF EXISTS cases_status")
    con.execute(
        """
        CREATE TABLE cases_status (
            case_pk INTEGER,
            institution_pk INTEGER,
            institution_name TEXT,
            status TEXT,
            reason TEXT,
            parsed_candidate_rows INTEGER,
            requested_more_time INTEGER,
            asked_about_anonymization INTEGER,
            requested_clarification INTEGER,
            requested_processed_info_justification INTEGER,
            fee_notice INTEGER,
            transferred_or_not_competent INTEGER,
            formal_deficiency_request INTEGER,
            refusal_detected INTEGER,
            unprocessed_attachment INTEGER
        )
        """
    )
    con.executemany(
        """
        INSERT INTO cases_status (
            case_pk,
            institution_pk,
            institution_name,
            status,
            reason,
            parsed_candidate_rows,
            requested_more_time,
            asked_about_anonymization,
            requested_clarification,
            requested_processed_info_justification,
            fee_notice,
            transferred_or_not_competent,
            formal_deficiency_request,
            refusal_detected,
            unprocessed_attachment
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.case_pk,
                item.institution_pk,
                item.institution_name,
                item.status,
                item.reason,
                item.parsed_candidate_rows,
                int(item.flags.requested_more_time),
                int(item.flags.asked_about_anonymization),
                int(item.flags.requested_clarification),
                int(item.flags.requested_processed_info_justification),
                int(item.flags.fee_notice),
                int(item.flags.transferred_or_not_competent),
                int(item.flags.formal_deficiency_request),
                int(item.flags.refusal_detected),
                int(item.flags.unprocessed_attachment),
            )
            for item in statuses
        ],
    )
    con.commit()


def write_extracted_rows(
    con: sqlite3.Connection,
    rows: list[SalaryRow],
) -> None:
    """Replace the detailed extracted-salary table."""
    con.execute("DROP TABLE IF EXISTS salaries_extracted")
    con.execute(
        """
        CREATE TABLE salaries_extracted (
            case_pk INTEGER,
            institution_pk INTEGER,
            institution_name TEXT,
            source_name TEXT,
            recipient_type TEXT,
            recipient_name TEXT,
            doctor_name TEXT,
            doctor_initials TEXT,
            specialization TEXT,
            doctor_status TEXT,
            organizational_unit TEXT,
            contract_type TEXT,
            net_compensation REAL,
            gross_compensation REAL,
            page_number INTEGER,
            parser TEXT,
            confidence TEXT,
            raw_row TEXT,
            comment TEXT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO salaries_extracted (
            case_pk,
            institution_pk,
            institution_name,
            source_name,
            recipient_type,
            recipient_name,
            doctor_name,
            doctor_initials,
            specialization,
            doctor_status,
            organizational_unit,
            contract_type,
            net_compensation,
            gross_compensation,
            page_number,
            parser,
            confidence,
            raw_row,
            comment
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.case_pk,
                row.institution_pk,
                row.institution_name,
                row.source_name,
                row.recipient_type,
                row.recipient_name,
                row.doctor_name,
                row.doctor_initials,
                row.specialization,
                row.doctor_status,
                row.organizational_unit,
                row.contract_type,
                row.net_compensation,
                row.gross_compensation,
                row.page_number,
                row.parser,
                row.confidence,
                row.raw_row,
                row.comment,
            )
            for row in rows
        ],
    )
    con.commit()


def write_summary(con: sqlite3.Connection) -> None:
    """Rebuild institution totals with explicit doctor/company metric groups."""
    con.execute("DROP TABLE IF EXISTS salaries_summary")
    con.execute(
        """
        CREATE TABLE salaries_summary AS
        SELECT
            institution_pk,
            institution_name,

            COUNT(*) AS record_count,
            ROUND(SUM(COALESCE(gross_compensation, net_compensation)), 2)
                AS total_compensation,
            ROUND(MAX(COALESCE(gross_compensation, net_compensation)), 2)
                AS max_compensation,
            SUM(CASE
                WHEN COALESCE(gross_compensation, net_compensation) > 500000
                THEN 1 ELSE 0 END)
                AS count_above_500k,
            SUM(CASE
                WHEN COALESCE(gross_compensation, net_compensation) > 1000000
                THEN 1 ELSE 0 END)
                AS count_above_1m,

            SUM(CASE
                WHEN recipient_type IN ('doctor', 'anonymous_doctor')
                THEN 1 ELSE 0 END)
                AS doctor_record_count,
            ROUND(SUM(CASE
                WHEN recipient_type IN ('doctor', 'anonymous_doctor')
                THEN COALESCE(gross_compensation, net_compensation)
                ELSE 0 END), 2)
                AS doctor_total_compensation,
            ROUND(MAX(CASE
                WHEN recipient_type IN ('doctor', 'anonymous_doctor')
                THEN COALESCE(gross_compensation, net_compensation)
                ELSE NULL END), 2)
                AS doctor_max_compensation,
            SUM(CASE
                WHEN recipient_type IN ('doctor', 'anonymous_doctor')
                 AND COALESCE(gross_compensation, net_compensation) > 500000
                THEN 1 ELSE 0 END)
                AS doctor_count_above_500k,
            SUM(CASE
                WHEN recipient_type IN ('doctor', 'anonymous_doctor')
                 AND COALESCE(gross_compensation, net_compensation) > 1000000
                THEN 1 ELSE 0 END)
                AS doctor_count_above_1m,

            SUM(CASE
                WHEN recipient_type = 'company'
                THEN 1 ELSE 0 END)
                AS company_record_count,
            ROUND(SUM(CASE
                WHEN recipient_type = 'company'
                THEN COALESCE(gross_compensation, net_compensation)
                ELSE 0 END), 2)
                AS company_total_compensation,
            ROUND(MAX(CASE
                WHEN recipient_type = 'company'
                THEN COALESCE(gross_compensation, net_compensation)
                ELSE NULL END), 2)
                AS company_max_compensation,
            SUM(CASE
                WHEN recipient_type = 'company'
                 AND COALESCE(gross_compensation, net_compensation) > 500000
                THEN 1 ELSE 0 END)
                AS company_count_above_500k,
            SUM(CASE
                WHEN recipient_type = 'company'
                 AND COALESCE(gross_compensation, net_compensation) > 1000000
                THEN 1 ELSE 0 END)
                AS company_count_above_1m
        FROM salaries_extracted
        GROUP BY institution_pk, institution_name
        ORDER BY total_compensation DESC
        """
    )
    con.commit()



def write_cases_status_csv(
    con: sqlite3.Connection,
    output_path: Path,
) -> None:
    """Export `cases_status` to a semicolon-delimited CSV file."""
    cursor = con.execute(
        """
        SELECT *
        FROM cases_status
        ORDER BY case_pk
        """
    )
    _write_cursor_csv(cursor, output_path)

def write_extracted_csv(
    con: sqlite3.Connection,
    output_path: Path,
) -> None:
    """Export `salaries_extracted` to a semicolon-delimited CSV file."""
    cursor = con.execute(
        """
        SELECT *
        FROM salaries_extracted
        ORDER BY institution_name, case_pk, page_number, rowid
        """
    )
    _write_cursor_csv(cursor, output_path)


def write_summary_csv(
    con: sqlite3.Connection,
    output_path: Path,
) -> None:
    """Export `salaries_summary` to a semicolon-delimited CSV file."""
    cursor = con.execute(
        """
        SELECT *
        FROM salaries_summary
        """
    )
    _write_cursor_csv(cursor, output_path)


def _write_cursor_csv(
    cursor: sqlite3.Cursor,
    output_path: Path,
) -> None:
    """Write a SQLite cursor result to UTF-8 BOM CSV."""
    headers = [description[0] for description in cursor.description]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(headers)
        writer.writerows(cursor.fetchall())
