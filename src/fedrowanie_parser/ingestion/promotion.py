"""Controlled promotion from ingestion staging into canonical salary rows."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..io.storage import ensure_salary_provenance_columns
from .review import resolve_source_file
from .storage import init_staging

__all__ = [
    "PromotionPlan",
    "build_promotion_plan",
    "promote_approved",
    "rollback_promotion",
]

_AMOUNT_TOLERANCE = 0.01
_PAGE_RE = re.compile(r"(?:^|/)p\.(\d+)(?:/|$)")


@dataclass(frozen=True)
class PromotionPlan:
    """A verified document-level promotion preview."""

    source_file: str
    institution_name: str
    row_count: int
    gross_sum: float
    staging_fingerprint: str
    action: str
    reason: str = ""


def _canonical_totals(con: sqlite3.Connection) -> tuple[int, float]:
    count, gross = con.execute(
        """
        SELECT COUNT(*), ROUND(SUM(COALESCE(gross_compensation, net_compensation, 0)), 2)
        FROM salaries_extracted
        """
    ).fetchone()
    return int(count or 0), float(gross or 0.0)


def _rows_for_document(con: sqlite3.Connection, source_file: str) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    return list(
        con.execute(
            """
            SELECT rowid AS staging_rowid, *
            FROM ingestion_rows
            WHERE source_file = ?
            ORDER BY rowid
            """,
            (source_file,),
        )
    )


def _fingerprint_rows(rows: list[sqlite3.Row]) -> str:
    payload = []
    for row in rows:
        payload.append(
            {
                "source_locator": row["source_locator"],
                "institution_pk": row["institution_pk"],
                "institution_name": row["institution_name"],
                "source_name": row["source_name"],
                "doctor_name": row["doctor_name"],
                "recipient_type": row["recipient_type"],
                "contract_type": row["contract_type"],
                "specialization": row["specialization"],
                "net_compensation": row["net_compensation"],
                "gross_compensation": row["gross_compensation"],
                "raw_row": row["raw_row"],
                "parser": row["parser"],
                "confidence": row["confidence"],
                "comment": row["comment"],
            }
        )
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _verify_document(con: sqlite3.Connection, doc: sqlite3.Row) -> PromotionPlan:
    rows = _rows_for_document(con, doc["source_file"])
    actual_count = len(rows)
    actual_gross = round(sum(float(row["gross_compensation"] or 0.0) for row in rows), 2)
    fingerprint = _fingerprint_rows(rows)
    expected_count = int(doc["accepted_rows"] or 0)
    expected_gross = round(float(doc["gross_sum"] or 0.0), 2)

    errors = []
    if actual_count != expected_count:
        errors.append(f"count staging={actual_count}, document={expected_count}")
    if abs(actual_gross - expected_gross) > _AMOUNT_TOLERANCE:
        errors.append(f"gross staging={actual_gross:.2f}, document={expected_gross:.2f}")
    if doc["staging_fingerprint"] and fingerprint != doc["staging_fingerprint"]:
        errors.append("staging fingerprint changed")

    active = con.execute(
        """
        SELECT promotion_id, staging_fingerprint
        FROM ingestion_promotions
        WHERE source_file = ? AND status = 'PROMOTED'
        ORDER BY promotion_id DESC LIMIT 1
        """,
        (doc["source_file"],),
    ).fetchone()
    if active:
        if active[1] == fingerprint:
            return PromotionPlan(
                doc["source_file"], doc["institution_name"], actual_count, actual_gross,
                fingerprint, "SKIP", "already promoted",
            )
        errors.append("an older version of this source is already promoted; rollback it first")

    action = "BLOCK" if errors else "INSERT"
    return PromotionPlan(
        doc["source_file"], doc["institution_name"], actual_count, actual_gross,
        fingerprint, action, "; ".join(errors),
    )


def build_promotion_plan(
    con: sqlite3.Connection,
    source_files: list[str] | None = None,
) -> list[PromotionPlan]:
    """Verify approved staging documents and return an insert/skip/block plan."""
    init_staging(con)
    ensure_salary_provenance_columns(con)
    con.row_factory = sqlite3.Row
    params: list[str] = []
    where = "review_status = 'APPROVED'"
    if source_files:
        resolved = [resolve_source_file(con, item) for item in source_files]
        placeholders = ",".join("?" for _ in resolved)
        where += f" AND source_file IN ({placeholders})"
        params.extend(resolved)
    docs = list(
        con.execute(
            f"""
            SELECT * FROM ingestion_documents
            WHERE {where}
            ORDER BY source_file
            """,
            params,
        )
    )
    return [_verify_document(con, doc) for doc in docs]


def _page_number(locator: str) -> int | None:
    match = _PAGE_RE.search(locator or "")
    return int(match.group(1)) if match else None


def _insert_document(
    con: sqlite3.Connection,
    plan: PromotionPlan,
) -> tuple[int, float, int]:
    rows = _rows_for_document(con, plan.source_file)
    before_count, before_gross = _canonical_totals(con)
    cursor = con.execute(
        """
        INSERT INTO ingestion_promotions (
            source_file, staging_fingerprint, institution_name, status,
            expected_count, expected_gross, promoted_at
        ) VALUES (?, ?, ?, 'PROMOTING', ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            plan.source_file,
            plan.staging_fingerprint,
            plan.institution_name,
            plan.row_count,
            plan.gross_sum,
        ),
    )
    promotion_id = int(cursor.lastrowid)
    for row in rows:
        source_name = (row["source_name"] or "").strip()
        doctor_name = (row["doctor_name"] or "").strip()
        recipient_type = (row["recipient_type"] or "anonymous_doctor").strip()
        recipient_name = doctor_name or source_name
        con.execute(
            """
            INSERT INTO salaries_extracted (
                case_pk, institution_pk, institution_name, source_name,
                recipient_type, recipient_name, doctor_name, doctor_initials,
                specialization, doctor_status, organizational_unit, contract_type,
                net_compensation, gross_compensation, page_number, parser,
                confidence, raw_row, comment, ingestion_source_file,
                ingestion_source_locator, ingestion_fingerprint, ingestion_promotion_id
            ) VALUES (
                NULL, ?, ?, ?, ?, ?, ?, '', ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                row["institution_pk"], row["institution_name"], source_name,
                recipient_type, recipient_name, doctor_name,
                row["specialization"] or "", row["contract_type"] or "",
                row["net_compensation"], row["gross_compensation"],
                _page_number(row["source_locator"]), row["parser"], row["confidence"],
                row["raw_row"], row["comment"], plan.source_file,
                row["source_locator"], plan.staging_fingerprint, promotion_id,
            ),
        )

    after_count, after_gross = _canonical_totals(con)
    added_count = after_count - before_count
    added_gross = round(after_gross - before_gross, 2)
    if added_count != plan.row_count or abs(added_gross - plan.gross_sum) > _AMOUNT_TOLERANCE:
        raise RuntimeError(
            "promotion invariant failed: "
            f"expected +{plan.row_count}/+{plan.gross_sum:.2f}, "
            f"got +{added_count}/+{added_gross:.2f}"
        )
    con.execute(
        """
        UPDATE ingestion_promotions
        SET status = 'PROMOTED', actual_count = ?, actual_gross = ?
        WHERE promotion_id = ?
        """,
        (added_count, added_gross, promotion_id),
    )
    con.execute(
        """
        UPDATE ingestion_documents
        SET promoted_at = CURRENT_TIMESTAMP, promotion_id = ?
        WHERE source_file = ?
        """,
        (promotion_id, plan.source_file),
    )
    return added_count, added_gross, promotion_id


def promote_approved(
    con: sqlite3.Connection,
    *,
    dry_run: bool = True,
    source_files: list[str] | None = None,
) -> dict[str, object]:
    """Promote approved documents, one atomic transaction per source document."""
    plans = build_promotion_plan(con, source_files)
    before_count, before_gross = _canonical_totals(con)
    inserted_count = 0
    inserted_gross = 0.0
    promotion_ids: list[int] = []

    if not dry_run:
        blocked = [plan for plan in plans if plan.action == "BLOCK"]
        if blocked:
            details = "; ".join(f"{Path(p.source_file).name}: {p.reason}" for p in blocked)
            raise RuntimeError(f"promotion blocked: {details}")
        for plan in plans:
            if plan.action != "INSERT":
                continue
            try:
                con.execute("BEGIN IMMEDIATE")
                count, gross, promotion_id = _insert_document(con, plan)
                con.commit()
            except Exception:
                con.rollback()
                raise
            inserted_count += count
            inserted_gross = round(inserted_gross + gross, 2)
            promotion_ids.append(promotion_id)

    projected_count = before_count + sum(p.row_count for p in plans if p.action == "INSERT")
    projected_gross = round(before_gross + sum(p.gross_sum for p in plans if p.action == "INSERT"), 2)
    return {
        "plans": plans,
        "before_count": before_count,
        "before_gross": before_gross,
        "projected_count": projected_count,
        "projected_gross": projected_gross,
        "inserted_count": inserted_count,
        "inserted_gross": inserted_gross,
        "promotion_ids": promotion_ids,
    }


def rollback_promotion(con: sqlite3.Connection, selector: str) -> dict[str, object]:
    """Rollback the active promotion for one staged source, verifying count and sum."""
    init_staging(con)
    ensure_salary_provenance_columns(con)
    source_file = resolve_source_file(con, selector)
    row = con.execute(
        """
        SELECT promotion_id, expected_count, expected_gross
        FROM ingestion_promotions
        WHERE source_file = ? AND status = 'PROMOTED'
        ORDER BY promotion_id DESC LIMIT 1
        """,
        (source_file,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No active promotion for {Path(source_file).name}")
    promotion_id, expected_count, expected_gross = int(row[0]), int(row[1]), float(row[2])
    actual_count, actual_gross = con.execute(
        """
        SELECT COUNT(*), ROUND(SUM(COALESCE(gross_compensation, net_compensation, 0)), 2)
        FROM salaries_extracted
        WHERE ingestion_promotion_id = ?
        """,
        (promotion_id,),
    ).fetchone()
    actual_count = int(actual_count or 0)
    actual_gross = float(actual_gross or 0.0)
    if actual_count != expected_count or abs(actual_gross - expected_gross) > _AMOUNT_TOLERANCE:
        raise RuntimeError(
            "rollback invariant failed before delete: "
            f"expected {expected_count}/{expected_gross:.2f}, "
            f"found {actual_count}/{actual_gross:.2f}"
        )
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM salaries_extracted WHERE ingestion_promotion_id = ?", (promotion_id,))
        con.execute(
            """
            UPDATE ingestion_promotions
            SET status = 'ROLLED_BACK', rolled_back_at = CURRENT_TIMESTAMP
            WHERE promotion_id = ?
            """,
            (promotion_id,),
        )
        con.execute(
            """
            UPDATE ingestion_documents
            SET promoted_at = NULL, promotion_id = NULL
            WHERE source_file = ?
            """,
            (source_file,),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    return {
        "source_file": source_file,
        "promotion_id": promotion_id,
        "removed_count": actual_count,
        "removed_gross": actual_gross,
    }
