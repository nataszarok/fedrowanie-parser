from fedrowanie_parser.ingestion.money import parse_money
from fedrowanie_parser.ingestion.mapper import map_table
from fedrowanie_parser.ingestion.models import CellTable
from pathlib import Path

def test_polish_money():
    assert parse_money('1 234 567,89 zł') == 1234567.89
    assert parse_money(1234.5) == 1234.5

def test_named_table_mapping():
    t=CellTable(Path('x.xlsx'),'s',None,[['Nazwisko','Imię','Wynagrodzenie brutto za 2025 r.'],['Kowalski','Jan','123 456,78 zł']], 'openpyxl')
    rows=map_table(t,'Szpital',None)
    assert len(rows)==1
    assert rows[0].doctor_name=='Kowalski Jan'
    assert rows[0].gross_compensation==123456.78

def test_summary_cells_not_rows():
    t=CellTable(Path('x.xlsx'),'s',None,[['Lekarz','Wynagrodzenie brutto'],['Lekarz 1',100000],['suma',100000]], 'openpyxl')
    rows=map_table(t,'Szpital',None)
    assert len(rows)==1


def test_ocr_amount_candidate_merge_prefers_salary_over_glued_lp():
    from fedrowanie_parser.ingestion.extractors.pdf import _merge_amount_candidates

    merged = _merge_amount_candidates([
        (100.0, 8233541.74),
        (103.0, 233541.74),
        (200.0, 456532.90),
    ])

    assert merged == [(101.5, 233541.74), (200.0, 456532.90)]
