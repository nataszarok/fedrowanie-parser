"""SQLite and CSV persistence."""
from __future__ import annotations
import csv
import sqlite3
from pathlib import Path
from ..models import SalaryRow

__all__ = [
    "write_sqlite",
    "write_csvs",
]


def write_sqlite(con: sqlite3.Connection, rows: list[SalaryRow]) -> None:
    """Write detailed salary rows and institution summaries to SQLite."""
    con.execute('DROP TABLE IF EXISTS salaries_extracted')
    con.execute("""
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
    
""")
    con.executemany("""
        INSERT INTO salaries_extracted
        (case_pk, institution_pk, placówka, Nazwa, "imię i nazwisko", "inicjały", specjalizacja, "stanowisko/status", "jednostka/oddział", "typ umowy",
         "wynagrodzenie netto", "wynagrodzenie brutto", strona, parser, pewność, raw_row, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    
""", [(r.case_pk, r.institution_pk, r.placowka, r.nazwa, r.imie_nazwisko, r.inicjaly, r.specjalizacja, r.stanowisko_status, r.jednostka_oddzial, r.typ_umowy, r.netto, r.brutto, r.strona, r.parser, r.pewnosc, r.raw_row, r.komentarz) for r in rows])
    con.execute('DROP TABLE IF EXISTS salaries_summary')
    con.execute("""
        CREATE TABLE salaries_summary AS
        SELECT institution_pk, placówka,
               COUNT(*) AS liczba_rekordów,
               ROUND(SUM(COALESCE("wynagrodzenie brutto", "wynagrodzenie netto")), 2) AS suma,
               ROUND(MAX(COALESCE("wynagrodzenie brutto", "wynagrodzenie netto")), 2) AS max,
               SUM(CASE WHEN COALESCE("wynagrodzenie brutto", "wynagrodzenie netto") > 500000 THEN 1 ELSE 0 END) AS liczba_powyżej_500k,
               SUM(CASE WHEN COALESCE("wynagrodzenie brutto", "wynagrodzenie netto") > 1000000 THEN 1 ELSE 0 END) AS liczba_powyżej_1mln
        FROM salaries_extracted
        GROUP BY institution_pk, placówka
        ORDER BY suma DESC
    
""")
    con.commit()

def write_csvs(con: sqlite3.Connection, rows_csv: Path, summary_csv: Path) -> None:
    """Export detailed salary rows and institution summaries as CSV files."""
    cur = con.execute('SELECT * FROM salaries_extracted ORDER BY placówka, case_pk, strona, rowid')
    headers = [d[0] for d in cur.description]
    with rows_csv.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(headers)
        w.writerows(cur.fetchall())
    cur = con.execute('SELECT * FROM salaries_summary')
    headers = [d[0] for d in cur.description]
    with summary_csv.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(headers)
        w.writerows(cur.fetchall())

