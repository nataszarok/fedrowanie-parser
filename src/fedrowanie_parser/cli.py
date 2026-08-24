"""Thin command-line entry point.

All extraction logic lives outside this module.
"""
from __future__ import annotations
import argparse
import shutil
import sqlite3
from pathlib import Path
from .pipeline import extract_cases
from .io.source_repository import load_source_cases
from .io.storage import (
    write_case_statuses,
    write_extracted_csv,
    write_extracted_rows,
    write_summary,
    write_summary_csv,
)


__all__ = [
    "main",
]

def main() -> None:
    """Run the CLI: parse arguments, extract rows, and write SQLite/CSV outputs."""
    ap = argparse.ArgumentParser()
    ap.add_argument('db', nargs='?', default='fedrowanie.db', help='wejściowa baza SQLite')
    ap.add_argument('--out-db', default='fedrowanie_wynagrodzenia_2025.db')
    ap.add_argument('--rows-csv', default='wynagrodzenia_lekarzy_2025.csv')
    ap.add_argument('--summary-csv', default='podsumowanie_placowek_2025.csv')
    args = ap.parse_args()
    src = Path(args.db)
    out_db = Path(args.out_db)
    if src.resolve() != out_db.resolve():
        shutil.copy2(src, out_db)
    con = sqlite3.connect(out_db)
    source_cases = load_source_cases(con)
    result = extract_cases(source_cases)
    write_case_statuses(con, result.statuses)
    write_extracted_rows(con, result.rows)
    write_summary(con)
    write_extracted_csv(con, Path(args.rows_csv))
    write_summary_csv(con, Path(args.summary_csv))
    institution_count = len({
        (row.institution_pk, row.placowka)
        for row in result.rows
    })
    print(
        f'Zapisano {len(result.rows):,} rekordów z {institution_count} placówek.'
        .replace(',', ' ')
    )
    print(f'DB: {out_db}')
    print(f'CSV: {args.rows_csv}')
    print(f'Podsumowanie: {args.summary_csv}')
    con.close()



if __name__ == "__main__":
    main()
