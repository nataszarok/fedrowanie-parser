"""CLI for generic ingestion into staging tables."""
from __future__ import annotations

import argparse
from pathlib import Path

from .evaluation import markdown_report
from .process import ingest_directory
from .runtime import runtime_diagnostics


def _print_dependency_check() -> None:
    print("Runtime dependencies:")
    for name, status, detail in runtime_diagnostics():
        print(f"- {name}: {status} — {detail}")


def main(argv=None):
    p=argparse.ArgumentParser(description='Generic salary-document ingestion into staging tables')
    p.add_argument('--db',type=Path)
    p.add_argument('--input',type=Path)
    p.add_argument('--report',type=Path)
    p.add_argument('--check-deps',action='store_true',help='show system dependencies used for .xls and scanned PDFs')
    a=p.parse_args(argv)
    if a.check_deps:
        _print_dependency_check()
        return 0
    if a.db is None or a.input is None:
        p.error('--db and --input are required unless --check-deps is used')
    docs=ingest_directory(a.input,a.db)
    report=markdown_report(docs)
    if a.report: a.report.write_text(report,encoding='utf-8')
    print(report)
    return 0
if __name__=='__main__': raise SystemExit(main())
