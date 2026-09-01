from fedrowanie_parser.models import SalaryRow
from fedrowanie_parser.enrichment.recipient import classify_salary_recipients


def _row(source_name: str, raw_row: str = "") -> SalaryRow:
    return SalaryRow(
        case_pk=1,
        institution_pk=1,
        institution_name="Test",
        source_name=source_name,
        specialization="",
        contract_type="",
        net_compensation=None,
        gross_compensation=100.0,
        page_number=None,
        parser="test",
        confidence="high",
        raw_row=raw_row,
    )


def test_juramedic_sp_zoo_is_company():
    row = _row("JURAMEDIC sp. z o.o.")
    result = classify_salary_recipients([row], "JURAMEDIC sp. z o.o.")
    assert result[0].recipient_type == "company"
    assert result[0].recipient_name == "JURAMEDIC sp. z o.o."


def test_legal_form_in_raw_row_is_company():
    row = _row("JURAMEDIC", "JURAMEDIC Sp. z o.o. | 2400000,00")
    result = classify_salary_recipients([row], row.raw_row)
    assert result[0].recipient_type == "company"


def test_named_doctor_is_not_company():
    row = _row("Jan Kowalski")
    row.doctor_name = "Jan Kowalski"
    result = classify_salary_recipients([row], "Jan Kowalski")
    assert result[0].recipient_type == "doctor"


def test_person_name_kordas_andrzej_is_not_company():
    row = _row("Kordas | Andrzej | 539 788,00 zł")
    result = classify_salary_recipients([row], row.source_name)
    assert result[0].recipient_type == "anonymous_doctor"


def test_person_name_kundera_aleksandra_maria_is_not_company():
    row = _row("Kundera | Aleksandra Maria | 34 860,00 zł")
    result = classify_salary_recipients([row], row.source_name)
    assert result[0].recipient_type == "anonymous_doctor"


def test_person_name_mikolajczak_aleksandra_is_not_company():
    row = _row("Mikołajczak | Aleksandra | 518 810,00 zł")
    result = classify_salary_recipients([row], row.source_name)
    assert result[0].recipient_type == "anonymous_doctor"


def test_sa_legal_form_is_company():
    row = _row("MEDICUS S.A.")
    result = classify_salary_recipients([row], row.source_name)
    assert result[0].recipient_type == "company"


def test_sp_k_legal_form_is_company():
    row = _row("MEDICUS sp.k.")
    result = classify_salary_recipients([row], row.source_name)
    assert result[0].recipient_type == "company"


def test_sa_alone_in_numbered_row_is_initials_not_company():
    row = _row("S.A", "14 | S.A | 482 670,00")
    result = classify_salary_recipients([row], row.raw_row)
    assert result[0].recipient_type == "anonymous_doctor"


def test_ab_alone_is_initials_not_company():
    row = _row("A.B.", "14 | A.B. | 482 670,00")
    result = classify_salary_recipients([row], row.raw_row)
    assert result[0].recipient_type == "anonymous_doctor"


def test_sa_in_numbered_raw_row_is_initials_even_when_source_is_generated_label():
    row = _row("Lekarz 55", "55 | S.A | 145 560,00")
    result = classify_salary_recipients([row], row.raw_row)
    assert result[0].recipient_type == "anonymous_doctor"


def test_ocr_initials_in_numbered_raw_row_are_not_company():
    row = _row("Lekarz 6", "6 | Š.A | 643 651,00")
    result = classify_salary_recipients([row], row.raw_row)
    assert result[0].recipient_type == "anonymous_doctor"
