import sqlite3

from fedrowanie_parser.models import SalaryRow
from fedrowanie_parser.ingestion.models import IngestedSalary, DocumentIngestion
from fedrowanie_parser.ingestion.storage import replace_document
from fedrowanie_parser.io.storage import write_extracted_rows


def test_salary_row_normalizes_blank_optional_text_to_none():
    row = SalaryRow(
        1, 2, "Hospital", "Lekarz 1", "", "", None, 1000.0, 1,
        "test", "wysoka", "raw", comment=" ", organizational_unit="",
        doctor_name="", doctor_status="", doctor_initials="", recipient_name="",
    )
    assert row.specialization is None
    assert row.contract_type is None
    assert row.comment is None
    assert row.organizational_unit is None
    assert row.doctor_name is None
    assert row.doctor_status is None
    assert row.doctor_initials is None
    assert row.recipient_name is None


def test_ingested_salary_normalizes_blank_optional_text_to_none():
    row = IngestedSalary(
        "x.xlsx", "Sheet1:row 2", "Hospital", 2, "Lekarz 1",
        doctor_name="", doctor_initials=" ", contract_type="",
        specialization="", comment="",
    )
    assert row.doctor_name is None
    assert row.doctor_initials is None
    assert row.contract_type is None
    assert row.specialization is None
    assert row.comment is None


def test_storage_persists_missing_optional_text_as_sql_null():
    con = sqlite3.connect(":memory:")
    row = SalaryRow(
        1, 2, "Hospital", "Lekarz 1", "", "", None, 1000.0, 1,
        "test", "wysoka", "raw", doctor_name="", doctor_initials="",
        recipient_type="anonymous_doctor", recipient_name="",
    )
    write_extracted_rows(con, [row])
    saved = con.execute(
        "SELECT recipient_name, doctor_name, doctor_initials, specialization, doctor_status, organizational_unit, contract_type FROM salaries_extracted"
    ).fetchone()
    assert saved == (None, None, None, None, None, None, None)


def test_staging_persists_missing_optional_text_as_sql_null():
    con = sqlite3.connect(":memory:")
    row = IngestedSalary(
        "x.xlsx", "Sheet1:row 2", "Hospital", 2, "Lekarz 1",
        doctor_name="", doctor_initials="", contract_type="", specialization="", comment="",
        gross_compensation=1000.0,
    )
    doc = DocumentIngestion(
        "x.xlsx", ".xlsx", "Hospital", 2, "OK", "test",
        rows=[row],
    )
    replace_document(con, doc)
    saved = con.execute(
        "SELECT doctor_name, doctor_initials, contract_type, specialization, comment FROM ingestion_rows"
    ).fetchone()
    assert saved == (None, None, None, None, None)


def test_comment_append_accepts_none_and_never_invents_empty_text():
    from fedrowanie_parser.pipeline import _append_comment

    assert _append_comment(None, "nowy komentarz") == "nowy komentarz"
    assert _append_comment("stary komentarz", "nowy komentarz") == (
        "stary komentarz; nowy komentarz"
    )
    assert _append_comment(None, None) is None
    assert _append_comment("   ", " ; ") is None


def test_section_salary_rebuild_handles_missing_old_comment():
    from fedrowanie_parser.pipeline import _rebuild_section_salary_rows
    from fedrowanie_parser.special_cases.section_salary_list import SectionSalaryItem

    old = SalaryRow(
        10,
        20,
        "Hospital",
        "Lekarz 1",
        None,
        None,
        None,
        12345.67,
        4,
        "old-parser",
        "średnia",
        "1 | 12345,67",
        comment=None,
    )
    item = SectionSalaryItem(
        index=1,
        role="lekarz",
        amount=12345.67,
        unit="Oddział A",
        raw_row="1. lekarz — 12 345,67 zł",
    )

    rebuilt = _rebuild_section_salary_rows(10, 20, "Hospital", [old], [item])

    assert len(rebuilt) == 1
    row = rebuilt[0]
    assert row.comment == "rekord z sekcyjnej listy wynagrodzeń"
    assert row.specialization is None
    assert row.contract_type is None
    assert row.organizational_unit == "Oddział A"


def test_salary_row_can_be_recanonicalized_after_enrichment_mutation():
    row = SalaryRow(
        1, 2, "Hospital", "Lekarz 1", None, None, None, 1000.0, 1,
        "test", "wysoka", "raw",
    )
    # Enrichment is allowed to mutate dataclass fields after __post_init__.
    row.doctor_name = ""
    row.comment = "   "
    row.specialization = ""

    row.normalize_missing_text()

    assert row.doctor_name is None
    assert row.comment is None
    assert row.specialization is None
