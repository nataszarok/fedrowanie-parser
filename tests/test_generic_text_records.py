from pathlib import Path
from fedrowanie_parser.ingestion.text_records import parse_salary_text_line
from fedrowanie_parser.ingestion.process import _document_year_status
from fedrowanie_parser.ingestion.models import CellTable

def test_numbered_jdg_list():
    r=parse_salary_text_line('1) Praktyka Lekarska Michał Szcześnik – 443.345,00 zł brutto,')
    assert r and r.source_name=='Praktyka Lekarska Michał Szcześnik'
    assert r.amount==443345.00 and r.kind=='gross'

def test_ocr_table_line():
    r=parse_salary_text_line('[Andrzejewski Marek 317250,24|')
    assert r and r.source_name=='Andrzejewski Marek' and r.amount==317250.24

def test_2026_letter_date_does_not_skip_2025_batch():
    t=CellTable(Path('x.pdf'),'text',1,[['Kościan, dn. 13.07.2026 r.'],['w załączeniu przekazujemy żądane informacje']], 'pymupdf-text')
    assert _document_year_status(Path('SPZOZ Kościan.pdf'),[t])[0] is True

def test_explicit_data_for_2026_is_skipped():
    t=CellTable(Path('x.docx'),'table',None,[['Dane za','MAJ 2026 r.']], 'python-docx')
    assert _document_year_status(Path('Kołobrzeg.docx'),[t])[0] is False
