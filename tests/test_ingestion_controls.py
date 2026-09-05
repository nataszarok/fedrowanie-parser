from pathlib import Path
from fedrowanie_parser.ingestion.models import CellTable
from fedrowanie_parser.ingestion.controls import source_controls, compare_controls
from fedrowanie_parser.ingestion.person import person_from_source

def test_controls_group_sums_are_accepted():
    t=CellTable(Path('x.xlsx'),'s',None,[['count',50],['count',23],['suma',1000],['suma',2000]],'openpyxl')
    c=source_controls([t])
    v=compare_controls(73,3000,c)
    assert v['count_match'] is True
    assert v['gross_match'] is True

def test_person_from_practice_prefix_suffix():
    assert person_from_source('Piotr Rola Indywidualna Praktyka Lekarska') == 'Piotr Rola'
    assert person_from_source('Praktyka Lekarska Bajraszewski Omar') == 'Bajraszewski Omar'
    assert person_from_source('Indywidualna Praktyka Lekarska Krzysztof Klepacki') == 'Krzysztof Klepacki'
