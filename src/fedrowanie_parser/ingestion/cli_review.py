"""CLI for reviewing staged ingestion documents."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .review import list_documents, resolve_source_file, set_review_status

__all__ = ["main"]


def _print_rows(con: sqlite3.Connection) -> None:
    rows = list_documents(con)
    print("review\tparser\trows\tgross\tinstitution\tfile")
    for row in rows:
        print(
            f"{row['review_status']}\t{row['status']}\t{row['accepted_rows']}\t"
            f"{float(row['gross_sum'] or 0):.2f}\t{row['institution_name']}\t"
            f"{Path(row['source_file']).name}"
        )


def main(argv: list[str] | None = None) -> int:
    """Review staged documents: list, approve, reject, or reset to pending."""
    parser = argparse.ArgumentParser(description="Human review of generic-ingestion documents")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--list", action="store_true", help="list staged documents")
    parser.add_argument("--approve", action="append", default=[], metavar="FILE")
    parser.add_argument("--reject", action="append", default=[], metavar="FILE")
    parser.add_argument("--pending", action="append", default=[], metavar="FILE")
    parser.add_argument("--approve-all-ok", action="store_true")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)

    con = sqlite3.connect(args.db)
    try:
        if args.approve_all_ok:
            files = [
                row[0]
                for row in con.execute(
                    """
                    SELECT source_file FROM ingestion_documents
                    WHERE status = 'OK' AND accepted_rows > 0
                    """
                )
            ]
            for source_file in files:
                set_review_status(con, source_file, "APPROVED", args.note)
        for selector in args.approve:
            set_review_status(con, resolve_source_file(con, selector), "APPROVED", args.note)
        for selector in args.reject:
            set_review_status(con, resolve_source_file(con, selector), "REJECTED", args.note)
        for selector in args.pending:
            set_review_status(con, resolve_source_file(con, selector), "PENDING", args.note)
        _print_rows(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
