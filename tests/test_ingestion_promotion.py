"""Regression tests for controlled staging promotion."""
from __future__ import annotations

import sqlite3

from fedrowanie_parser.ingestion.models import DocumentIngestion, IngestedSalary
from fedrowanie_parser.ingestion.cli_promote import main as promote_main
from fedrowanie_parser.ingestion.promotion import promote_approved, rollback_promotion
from fedrowanie_parser.ingestion.review import set_review_status
from fedrowanie_parser.ingestion.storage import replace_document
from fedrowanie_parser.io.storage import write_extracted_rows


def _stage_example(con: sqlite3.Connection) -> None:
    document = DocumentIngestion(
        "example.pdf",
        ".pdf",
        "Example Hospital",
        10,
        "OK",
        "explicit_2025",
        1,
        2,
        2,
        300.0,
        0.0,
        [
            IngestedSalary(
                "example.pdf",
                "p.1/line 1",
                "Example Hospital",
                10,
                "Jan Kowalski",
                "Jan Kowalski",
                "doctor",
                gross_compensation=100.0,
            ),
            IngestedSalary(
                "example.pdf",
                "p.1/line 2",
                "Example Hospital",
                10,
                "Lekarz 2",
                "",
                "anonymous_doctor",
                gross_compensation=200.0,
            ),
        ],
    )
    replace_document(con, document)


def test_promotion_is_reviewed_idempotent_and_reversible(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _stage_example(con)

    assert promote_approved(con, dry_run=True)["plans"] == []
    set_review_status(con, "example.pdf", "APPROVED")

    preview = promote_approved(con, dry_run=True)
    assert preview["projected_count"] == 2
    assert preview["projected_gross"] == 300.0
    assert preview["plans"][0].action == "INSERT"
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 0

    committed = promote_approved(con, dry_run=False)
    assert committed["inserted_count"] == 2
    assert committed["inserted_gross"] == 300.0
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 2

    second = promote_approved(con, dry_run=True)
    assert second["plans"][0].action == "SKIP"
    assert second["plans"][0].reason == "already promoted"

    rolled = rollback_promotion(con, "example.pdf")
    assert rolled["removed_count"] == 2
    assert rolled["removed_gross"] == 300.0
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 0
    con.close()


def test_reingest_changed_output_resets_review(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _stage_example(con)
    set_review_status(con, "example.pdf", "APPROVED")

    changed = DocumentIngestion(
        "example.pdf",
        ".pdf",
        "Example Hospital",
        10,
        "OK",
        "explicit_2025",
        1,
        1,
        1,
        500.0,
        0.0,
        [
            IngestedSalary(
                "example.pdf",
                "p.1/line 1",
                "Example Hospital",
                10,
                "Jan Kowalski",
                "Jan Kowalski",
                "doctor",
                gross_compensation=500.0,
            )
        ],
    )
    replace_document(con, changed)
    status = con.execute(
        "SELECT review_status FROM ingestion_documents WHERE source_file='example.pdf'"
    ).fetchone()[0]
    assert status == "PENDING"
    con.close()



def _insert_existing_salary(
    con: sqlite3.Connection,
    *,
    institution_pk: int | None,
    institution_name: str,
    gross: float = 50.0,
) -> None:
    con.execute(
        """
        INSERT INTO salaries_extracted (
            case_pk, institution_pk, institution_name, source_name,
            recipient_type, recipient_name, doctor_name, doctor_initials,
            specialization, doctor_status, organizational_unit, contract_type,
            net_compensation, gross_compensation, page_number, parser,
            confidence, raw_row, comment
        ) VALUES (
            NULL, ?, ?, 'Existing Doctor', 'doctor', 'Existing Doctor',
            'Existing Doctor', '', '', '', '', '', NULL, ?, NULL,
            'existing', 'wysoka', '', ''
        )
        """,
        (institution_pk, institution_name, gross),
    )
    con.commit()


def test_promotion_skips_institution_already_present_by_pk(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _insert_existing_salary(
        con,
        institution_pk=10,
        institution_name="Example Hospital - canonical name",
    )
    _stage_example(con)
    set_review_status(con, "example.pdf", "APPROVED")

    preview = promote_approved(con, dry_run=True)
    assert preview["plans"][0].action == "SKIP"
    assert "institution already exists in salaries_extracted" in preview["plans"][0].reason
    assert "1 existing rows" in preview["plans"][0].reason

    committed = promote_approved(con, dry_run=False)
    assert committed["inserted_count"] == 0
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 1
    con.close()


def test_promotion_skips_existing_institution_by_normalized_name_without_pk(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _insert_existing_salary(
        con,
        institution_pk=None,
        institution_name="Szpital Św. Józefa",
    )
    document = DocumentIngestion(
        "duplicate.xlsx",
        ".xlsx",
        "SZPITAL SW JOZEFA",
        None,
        "OK",
        "explicit_2025",
        1,
        1,
        1,
        100.0,
        0.0,
        [
            IngestedSalary(
                "duplicate.xlsx",
                "sheet.1/row 1",
                "SZPITAL SW JOZEFA",
                None,
                "Jan Kowalski",
                "Jan Kowalski",
                "doctor",
                gross_compensation=100.0,
            )
        ],
    )
    replace_document(con, document)
    set_review_status(con, "duplicate.xlsx", "APPROVED")

    preview = promote_approved(con, dry_run=True)
    assert preview["plans"][0].action == "SKIP"
    assert "Szpital Św. Józefa" in preview["plans"][0].reason
    con.close()


def test_existing_institution_can_be_explicitly_allowed(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _insert_existing_salary(con, institution_pk=10, institution_name="Example Hospital")
    _stage_example(con)
    set_review_status(con, "example.pdf", "APPROVED")

    preview = promote_approved(
        con,
        dry_run=True,
        allow_existing_institutions=True,
    )
    assert preview["plans"][0].action == "INSERT"

    committed = promote_approved(
        con,
        dry_run=False,
        allow_existing_institutions=True,
    )
    assert committed["inserted_count"] == 2
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 3
    con.close()


def test_cli_commit_reports_skip_and_succeeds_for_duplicate_institution(tmp_path, capsys):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _insert_existing_salary(con, institution_pk=10, institution_name="Example Hospital")
    _stage_example(con)
    set_review_status(con, "example.pdf", "APPROVED")
    con.close()

    exit_code = promote_main(["--db", str(db_path), "--commit"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SKIP" in output
    assert "institution already exists in salaries_extracted" in output
    assert "inserted: rows=0" in output

    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 1
    con.close()


def test_commit_inserts_new_institution_and_skips_existing_one(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    _insert_existing_salary(con, institution_pk=10, institution_name="Example Hospital")
    _stage_example(con)
    set_review_status(con, "example.pdf", "APPROVED")

    new_document = DocumentIngestion(
        "new.xlsx",
        ".xlsx",
        "New Hospital",
        20,
        "OK",
        "explicit_2025",
        1,
        1,
        1,
        400.0,
        0.0,
        [
            IngestedSalary(
                "new.xlsx",
                "sheet.1/row 1",
                "New Hospital",
                20,
                "Anna Nowak",
                "Anna Nowak",
                "doctor",
                gross_compensation=400.0,
            )
        ],
    )
    replace_document(con, new_document)
    set_review_status(con, "new.xlsx", "APPROVED")

    committed = promote_approved(con, dry_run=False)
    by_file = {plan.source_file: plan for plan in committed["plans"]}

    assert by_file["example.pdf"].action == "SKIP"
    assert by_file["new.xlsx"].action == "INSERT"
    assert committed["inserted_count"] == 1
    assert committed["inserted_gross"] == 400.0
    assert con.execute("SELECT COUNT(*) FROM salaries_extracted").fetchone()[0] == 2
    assert con.execute(
        "SELECT COUNT(*) FROM salaries_extracted WHERE institution_pk = 10"
    ).fetchone()[0] == 1
    assert con.execute(
        "SELECT COUNT(*) FROM salaries_extracted WHERE institution_pk = 20"
    ).fetchone()[0] == 1
    con.close()


def test_promotion_does_not_commit_placeholder_as_doctor_name(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    document = DocumentIngestion(
        "initials.xlsx", ".xlsx", "Initials Hospital", 901, "OK", "explicit_2025",
        1, 1, 1, 12345.0, 0.0,
        [IngestedSalary(
            "initials.xlsx", "Sheet1:row 2", "Initials Hospital", 901,
            "K K", "K K", "doctor", gross_compensation=12345.0,
        )],
    )
    replace_document(con, document)
    set_review_status(con, "initials.xlsx", "APPROVED")
    result = promote_approved(con, dry_run=False)
    assert result["inserted_count"] == 1
    recipient_type, recipient_name, doctor_name, doctor_initials = con.execute(
        "SELECT recipient_type, recipient_name, doctor_name, doctor_initials FROM salaries_extracted"
    ).fetchone()
    assert recipient_type == "anonymous_doctor"
    assert recipient_name is None
    assert doctor_name is None
    assert doctor_initials == "K.K."
    con.close()


def test_promotion_ignores_xxx_placeholder_instead_of_initials(tmp_path):
    db_path = tmp_path / "placeholder.db"
    con = sqlite3.connect(db_path)
    write_extracted_rows(con, [])
    document = DocumentIngestion(
        "placeholder.xlsx", ".xlsx", "Placeholder Hospital", 902, "OK", "explicit_2025",
        1, 1, 1, 10000.0, 0.0,
        [IngestedSalary(
            "placeholder.xlsx", "Sheet1:row 2", "Placeholder Hospital", 902,
            "XXX XXX", "XXX XXX", "doctor", gross_compensation=10000.0,
        )],
    )
    replace_document(con, document)
    set_review_status(con, "placeholder.xlsx", "APPROVED")
    result = promote_approved(con, dry_run=False)
    assert result["inserted_count"] == 1
    recipient_type, recipient_name, doctor_name, doctor_initials = con.execute(
        "SELECT recipient_type, recipient_name, doctor_name, doctor_initials FROM salaries_extracted"
    ).fetchone()
    assert recipient_type == "anonymous_doctor"
    assert recipient_name is None
    assert doctor_name is None
    assert doctor_initials is None
    con.close()
