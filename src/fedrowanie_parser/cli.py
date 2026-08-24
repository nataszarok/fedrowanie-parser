"""Thin command-line entry point.

All extraction logic lives outside this module.
"""
from __future__ import annotations
import argparse
import shutil
import sqlite3
from pathlib import Path
from .pipeline import extract_all
from .io.storage import write_csvs, write_sqlite


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
    rows = extract_all(con)
    write_sqlite(con, rows)
    write_csvs(con, Path(args.rows_csv), Path(args.summary_csv))
    n_fac = con.execute('SELECT COUNT(*) FROM salaries_summary').fetchone()[0]
    print(f'Zapisano {len(rows):,} rekordów z {n_fac} placówek.'.replace(',', ' '))
    print(f'DB: {out_db}')
    print(f'CSV: {args.rows_csv}')
    print(f'Podsumowanie: {args.summary_csv}')
    con.close()



if __name__ == "__main__":
    main()
