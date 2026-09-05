"""CLI for generic ingestion into staging tables."""
from __future__ import annotations

import argparse
from pathlib import Path

from .evaluation import markdown_report
from .process import SUPPORTED, ingest_directory
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

    input_dir = a.input.expanduser().resolve()
    db_path = a.db.expanduser().resolve()
    if not input_dir.exists():
        p.error(f'input directory does not exist: {input_dir}')
    if not input_dir.is_dir():
        p.error(f'--input must point to a directory: {input_dir}')

    supported_files = [
        path for path in input_dir.rglob('*')
        if path.is_file()
        and path.suffix.lower() in SUPPORTED
        and '__MACOSX' not in path.parts
        and not path.name.startswith(('._', '~$'))
    ]
    if not supported_files:
        extensions = ', '.join(sorted(SUPPORTED))
        p.error(
            f'no supported input files found under {input_dir} '
            f'(supported: {extensions})'
        )

    print(
        f'[fedrowanie-ingest] input={input_dir} | files={len(supported_files)} | db={db_path}',
        flush=True,
    )
    print(
        '[fedrowanie-ingest] writing staging tables: ingestion_documents, ingestion_rows; '
        'salaries_extracted is populated only by fedrowanie-promote --commit',
        flush=True,
    )
    docs=ingest_directory(input_dir,db_path)
    report=markdown_report(docs)
    if a.report: a.report.write_text(report,encoding='utf-8')
    print(report)
    return 0
if __name__=='__main__': raise SystemExit(main())
