"""SQLite and CSV persistence."""
from __future__ import annotations
import csv
import sqlite3
from pathlib import Path
from ..models import SalaryRow

def write_sqlite(con: sqlite3.Connection, rows: list[SalaryRow]) -> None:
    """Persist extracted rows and aggregated institution summaries to SQLite."""
    con.execute('DROP TABLE IF EXISTS salaries_extracted')
    con.execute('\n        CREATE TABLE salaries_extracted (\n            case_pk INTEGER,\n            institution_pk INTEGER,\n            placówka TEXT,\n            Nazwa TEXT,\n            "imię i nazwisko" TEXT,\n            "inicjały" TEXT,\n            specjalizacja TEXT,\n            "stanowisko/status" TEXT,\n            "jednostka/oddział" TEXT,\n            "typ umowy" TEXT,\n            "wynagrodzenie netto" REAL,\n            "wynagrodzenie brutto" REAL,\n            strona INTEGER,\n            parser TEXT,\n            pewność TEXT,\n            raw_row TEXT,\n            komentarz TEXT\n        )\n    ')
    con.executemany('\n        INSERT INTO salaries_extracted\n        (case_pk, institution_pk, placówka, Nazwa, "imię i nazwisko", "inicjały", specjalizacja, "stanowisko/status", "jednostka/oddział", "typ umowy",\n         "wynagrodzenie netto", "wynagrodzenie brutto", strona, parser, pewność, raw_row, komentarz)\n        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n    ', [(r.case_pk, r.institution_pk, r.placowka, r.nazwa, r.imie_nazwisko, r.inicjaly, r.specjalizacja, r.stanowisko_status, r.jednostka_oddzial, r.typ_umowy, r.netto, r.brutto, r.strona, r.parser, r.pewnosc, r.raw_row, r.komentarz) for r in rows])
    con.execute('DROP TABLE IF EXISTS salaries_summary')
    con.execute('\n        CREATE TABLE salaries_summary AS\n        SELECT institution_pk, placówka,\n               COUNT(*) AS liczba_rekordów,\n               ROUND(SUM(COALESCE("wynagrodzenie brutto", "wynagrodzenie netto")), 2) AS suma,\n               ROUND(MAX(COALESCE("wynagrodzenie brutto", "wynagrodzenie netto")), 2) AS max,\n               SUM(CASE WHEN COALESCE("wynagrodzenie brutto", "wynagrodzenie netto") > 500000 THEN 1 ELSE 0 END) AS liczba_powyżej_500k,\n               SUM(CASE WHEN COALESCE("wynagrodzenie brutto", "wynagrodzenie netto") > 1000000 THEN 1 ELSE 0 END) AS liczba_powyżej_1mln\n        FROM salaries_extracted\n        GROUP BY institution_pk, placówka\n        ORDER BY suma DESC\n    ')
    con.commit()

def write_csvs(con: sqlite3.Connection, rows_csv: Path, summary_csv: Path) -> None:
    """Export detailed rows and institution summaries as CSV files."""
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

