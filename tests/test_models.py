"""Domain model schema invariants."""
from dataclasses import fields

from fedrowanie_parser.models import SalaryRow


def test_salary_row_uses_english_snake_case_fields():
    """SalaryRow fields must match the public extracted-data schema."""
    assert [field.name for field in fields(SalaryRow)] == [
        "case_pk",
        "institution_pk",
        "institution_name",
        "source_name",
        "specialization",
        "contract_type",
        "net_compensation",
        "gross_compensation",
        "page_number",
        "parser",
        "confidence",
        "raw_row",
        "comment",
        "organizational_unit",
        "doctor_name",
        "doctor_status",
        "doctor_initials",
        "recipient_type",
        "recipient_name",
    ]
