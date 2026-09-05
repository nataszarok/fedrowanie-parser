"""Regression tests for controlled staging promotion."""
from __future__ import annotations

import sqlite3

from fedrowanie_parser.ingestion.models import DocumentIngestion, IngestedSalary
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
