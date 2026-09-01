from fedrowanie_parser.models import SalaryRow
from fedrowanie_parser.pipeline import _classify_salary_recipients

def _row(source_name, amount):
    return SalaryRow(1, 2, "Hospital", source_name, "", "", None, amount, 1,
                     "vertical-label-amount", "wysoka", f"{source_name} | {amount}")

def test_anonymous_doctor():
    row = _classify_salary_recipients([_row("Lekarz 12", 123456.78)], "Lekarz 12\n123 456,78")[0]
    assert row.recipient_type == "anonymous_doctor"

def test_company_tail_label_recovers_full_name():
    doc = "Spółka udzielająca świadczeń\nz zakresu ortopedii\n8 591 317,35"
    row = _classify_salary_recipients([_row("z zakresu ortopedii", 8591317.35)], doc)[0]
    assert row.recipient_type == "company"
    assert row.recipient_name == "Spółka udzielająca świadczeń z zakresu ortopedii"
    assert row.doctor_name == ""
