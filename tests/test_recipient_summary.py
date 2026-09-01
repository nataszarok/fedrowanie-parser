import sqlite3

from fedrowanie_parser.io.storage import write_extracted_rows, write_summary
from fedrowanie_parser.models import SalaryRow
from fedrowanie_parser.enrichment.recipient import classify_salary_recipients


def _row(source_name, amount, doctor_name=''):
    return SalaryRow(
        1, 4565, 'Szpital Powiatowy w Sławnie', source_name, '', 'kontrakt',
        None, amount, 1, 'markdown-table', 'wysoka',
        f'1 | {source_name} | kontrakt | {amount}',
        doctor_name=doctor_name,
    )


def test_slawno_company_row_is_not_a_doctor():
    company = _row('Tomasz Bazar spółka (koordynator + 4 lekarzy)', 3668356.00)
    coordinator = _row('Tomasz Kasprzyk- koordynator', 969844.00, doctor_name='Tomasz Kasprzyk')

    company, coordinator = classify_salary_recipients([company, coordinator], '')

    assert company.recipient_type == 'company'
    assert company.recipient_name == 'Tomasz Bazar spółka (koordynator + 4 lekarzy)'
    assert company.doctor_name == ''
    assert coordinator.recipient_type == 'doctor'


def test_summary_keeps_all_totals_and_separates_doctors_and_companies():
    doctor = _row('Tomasz Kasprzyk- koordynator', 969844.00, doctor_name='Tomasz Kasprzyk')
    anonymous = _row('Lekarz specjalista', 741814.00)
    company = _row('Tomasz Bazar spółka (koordynator + 4 lekarzy)', 3668356.00)
    rows = classify_salary_recipients([doctor, anonymous, company], '')

    con = sqlite3.connect(':memory:')
    write_extracted_rows(con, rows)
    write_summary(con)
    result = con.execute('SELECT * FROM salaries_summary').fetchone()
    columns = [item[1] for item in con.execute('PRAGMA table_info(salaries_summary)')]
    data = dict(zip(columns, result))

    assert data['record_count'] == 3
    assert data['total_compensation'] == 5380014.00
    assert data['max_compensation'] == 3668356.00
    assert data['count_above_500k'] == 3
    assert data['count_above_1m'] == 1

    assert data['doctor_record_count'] == 2
    assert data['doctor_total_compensation'] == 1711658.00
    assert data['doctor_max_compensation'] == 969844.00
    assert data['doctor_count_above_500k'] == 2
    assert data['doctor_count_above_1m'] == 0

    assert data['company_record_count'] == 1
    assert data['company_total_compensation'] == 3668356.00
    assert data['company_max_compensation'] == 3668356.00
    assert data['company_count_above_500k'] == 1
    assert data['company_count_above_1m'] == 1
