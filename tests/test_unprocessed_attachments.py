"""Regression tests for unprocessed attachment diagnostics."""
from __future__ import annotations

import sqlite3

from fedrowanie_parser.io.source_repository import load_source_cases
from fedrowanie_parser.pipeline import extract_cases


def _source_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE institutions (pk INTEGER PRIMARY KEY, name TEXT)")
    con.execute(
        "CREATE TABLE cases (pk INTEGER PRIMARY KEY, institution_pk INTEGER, name TEXT)"
    )
    con.execute("CREATE TABLE case_pages (case_pk INTEGER, text TEXT)")
    con.execute(
        "CREATE TABLE attachments ("
        "id INTEGER PRIMARY KEY, letter_pk INTEGER, case_pk INTEGER, "
        "url TEXT, filename TEXT, ext TEXT)"
    )
    con.execute(
        "CREATE TABLE attachment_texts ("
        "id INTEGER PRIMARY KEY, case_pk INTEGER NOT NULL, idx INTEGER, "
        "filename TEXT, text TEXT, chars INTEGER, pages INTEGER, fetched_at TEXT)"
    )
    con.execute("INSERT INTO institutions VALUES (1, 'Hospital')")
    con.execute("INSERT INTO cases VALUES (10, 1, 'Hospital')")
    con.execute(
        "INSERT INTO case_pages VALUES "
        "(10, 'Dzień dobry. W odpowiedzi przekazujemy dane w załączeniu.')"
    )
    con.execute(
        "INSERT INTO attachments VALUES "
        "(1, 1, 10, '', 'wynagrodzenia.xlsx', 'xlsx')"
    )
    return con


def test_source_case_marks_attachment_without_extracted_text():
    """XLSX without attachment text must be exposed on the source case."""
    con = _source_db()
    cases = load_source_cases(con)

    assert cases[0].unprocessed_attachments == ("wynagrodzenia.xlsx",)


def test_source_case_does_not_mark_attachment_with_text():
    """An attachment with non-empty extracted text is considered processed."""
    con = _source_db()
    con.execute(
        "INSERT INTO attachment_texts "
        "(id, case_pk, filename, text) VALUES (1, 10, 'wynagrodzenia.xlsx', 'data')"
    )
    cases = load_source_cases(con)

    assert cases[0].unprocessed_attachments == ()
