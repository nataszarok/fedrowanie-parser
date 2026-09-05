"""CLI for dry-running, promoting, and rolling back reviewed ingestion documents."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .promotion import promote_approved, rollback_promotion

__all__ = ["main"]


def _print_result(result: dict[str, object], dry_run: bool) -> None:
    print("action\trows\tgross\tinstitution\tfile\treason")
    for plan in result["plans"]:
        print(
            f"{plan.action}\t{plan.row_count}\t{plan.gross_sum:.2f}\t"
            f"{plan.institution_name}\t{Path(plan.source_file).name}\t{plan.reason}"
        )
    print()
    print(
        f"before: rows={result['before_count']}, gross={result['before_gross']:.2f}"
    )
    print(
        f"{'projected' if dry_run else 'after'}: rows={result['projected_count']}, "
        f"gross={result['projected_gross']:.2f}"
    )
    if not dry_run:
        print(
            f"inserted: rows={result['inserted_count']}, gross={result['inserted_gross']:.2f}"
        )


def main(argv: list[str] | None = None) -> int:
    """Promote only human-approved staged documents into salaries_extracted."""
    parser = argparse.ArgumentParser(description="Controlled staging -> salaries_extracted promotion")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--source", action="append", default=[], metavar="FILE")
    parser.add_argument("--commit", action="store_true", help="perform inserts; default is dry-run")
    parser.add_argument(
        "--allow-existing-institution",
        action="store_true",
        help=(
            "include staged institutions that already have rows in salaries_extracted; "
            "by default such institutions are reported as SKIP and not inserted"
        ),
    )
    parser.add_argument("--rollback", metavar="FILE", help="rollback one active promotion")
    args = parser.parse_args(argv)

    con = sqlite3.connect(args.db)
    try:
        if args.rollback:
            rolled = rollback_promotion(con, args.rollback)
            print(
                f"rolled back {Path(rolled['source_file']).name}: "
                f"rows={rolled['removed_count']}, gross={rolled['removed_gross']:.2f}"
            )
            return 0
        result = promote_approved(
            con,
            dry_run=not args.commit,
            source_files=args.source or None,
            allow_existing_institutions=args.allow_existing_institution,
        )
        _print_result(result, dry_run=not args.commit)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
