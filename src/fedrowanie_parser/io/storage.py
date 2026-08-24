"""Persist parser outputs to SQLite and CSV."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from ..models import CaseParseStatus, SalaryRow

__all__ = [
    "write_case_statuses",
    "write_extracted_rows",
    "write_summary",
    "write_extracted_csv",
    "write_summary_csv",
]


def write_case_statuses(
    con: sqlite3.Connection,
    statuses: list[CaseParseStatus],
) -> None:
    """Replace the case-level parser diagnostics table."""
    con.execute("DROP TABLE IF EXISTS salaries_case_status")
    con.execute(
        """
        CREATE TABLE salaries_case_status (
            case_pk INTEGER,
            institution_pk INTEGER,
            placówka TEXT,
            status TEXT,
            reason TEXT,
            parsed_candidate_rows INTEGER
        )
        """
    )
    con.executemany(
        """
        INSERT INTO salaries_case_status (
            case_pk,
            institution_pk,
            placówka,
            status,
            reason,
            parsed_candidate_rows
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.case_pk,
                item.institution_pk,
                item.institution_name,
                item.status,
                item.reason,
                item.parsed_candidate_rows,
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
            placówka TEXT,
            Nazwa TEXT,
            "imię i nazwisko" TEXT,
            "inicjały" TEXT,
            specjalizacja TEXT,
            "stanowisko/status" TEXT,
            "jednostka/oddział" TEXT,
            "typ umowy" TEXT,
            "wynagrodzenie netto" REAL,
            "wynagrodzenie brutto" REAL,
            strona INTEGER,
            parser TEXT,
            pewność TEXT,
            raw_row TEXT,
            komentarz TEXT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO salaries_extracted (
            case_pk,
            institution_pk,
            placówka,
            Nazwa,
            "imię i nazwisko",
            "inicjały",
            specjalizacja,
            "stanowisko/status",
            "jednostka/oddział",
            "typ umowy",
            "wynagrodzenie netto",
            "wynagrodzenie brutto",
            strona,
            parser,
            pewność,
            raw_row,
            komentarz
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.case_pk,
                row.institution_pk,
                row.placowka,
                row.nazwa,
                row.imie_nazwisko,
                row.inicjaly,
                row.specjalizacja,
                row.stanowisko_status,
                row.jednostka_oddzial,
                row.typ_umowy,
                row.netto,
                row.brutto,
                row.strona,
                row.parser,
                row.pewnosc,
                row.raw_row,
                row.komentarz,
            )
            for row in rows
        ],
    )
    con.commit()


def write_summary(con: sqlite3.Connection) -> None:
    """Rebuild the institution summary from `salaries_extracted`."""
    con.execute("DROP TABLE IF EXISTS salaries_summary")
    con.execute(
        """
        CREATE TABLE salaries_summary AS
        SELECT
            institution_pk,
            placówka,
            COUNT(*) AS liczba_rekordów,
            ROUND(
                SUM(COALESCE("wynagrodzenie brutto", "wynagrodzenie netto")),
                2
            ) AS suma,
            ROUND(
                MAX(COALESCE("wynagrodzenie brutto", "wynagrodzenie netto")),
                2
            ) AS max,
            SUM(
                CASE
                    WHEN COALESCE(
                        "wynagrodzenie brutto",
                        "wynagrodzenie netto"
                    ) > 500000
                    THEN 1
                    ELSE 0
                END
            ) AS liczba_powyżej_500k,
            SUM(
                CASE
                    WHEN COALESCE(
                        "wynagrodzenie brutto",
                        "wynagrodzenie netto"
                    ) > 1000000
                    THEN 1
                    ELSE 0
                END
            ) AS liczba_powyżej_1mln
        FROM salaries_extracted
        GROUP BY institution_pk, placówka
        ORDER BY suma DESC
        """
    )
    con.commit()


def write_extracted_csv(
    con: sqlite3.Connection,
    output_path: Path,
) -> None:
    """Export `salaries_extracted` to a semicolon-delimited CSV file."""
    cursor = con.execute(
        """
        SELECT *
        FROM salaries_extracted
        ORDER BY placówka, case_pk, strona, rowid
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
