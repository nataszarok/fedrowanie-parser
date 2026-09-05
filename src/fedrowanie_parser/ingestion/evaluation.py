from __future__ import annotations
from pathlib import Path
from .models import DocumentIngestion

def _check(v):
    if v is None:
        return 'n/a'
    return 'OK' if v else 'MISMATCH'

def markdown_report(docs: list[DocumentIngestion]) -> str:
    ok=sum(d.status=='OK' for d in docs); total=len(docs)
    rows=sum(d.accepted_rows for d in docs); gross=sum(d.gross_sum for d in docs); net=sum(d.net_sum for d in docs)
    lines=[
        '# Generic ingestion evaluation','',
        f'- documents: **{total}**',
        f'- OK: **{ok}**',
        f'- extracted rows: **{rows}**',
        f'- gross/total sum: **{gross:,.2f}**',
        f'- net sum: **{net:,.2f}**','',
        '| file | status | tables | rows | gross/total | count check | gross check | institution match |',
        '|---|---:|---:|---:|---:|---|---|---|'
    ]
    for d in docs:
        lines.append(
            f"| {Path(d.source_file).name.replace('|','/')} | {d.status} | {d.tables_seen} | {d.accepted_rows} | "
            f"{d.gross_sum:,.2f} | {_check(d.count_match)} | {_check(d.gross_match)} | "
            f"{'pk='+str(d.institution_pk) if d.institution_pk is not None else 'unresolved'} |"
        )
    lines += [
        '', '## Guardrails', '',
        '- Original `salaries_extracted` is not modified by this process.',
        '- When a source contains `count/liczba` or `suma/razem` controls, extracted row count and gross sum are compared against them; split summary blocks are accepted when their controls add up to the extracted total.',
        '- Results go to `ingestion_documents` and `ingestion_rows` staging tables.',
        '- Files explicitly referring only to another year are skipped.',
        '- Spreadsheet side-panel diagnostics (`count`, `max`, `avg`, `suma`, `mediana`) are not treated as salary columns.',
        '- Legacy `.xls` is converted to `.xlsx` through LibreOffice before cell mapping.',
        '- OCR is a last-resort fallback only for PDFs without an extractable text layer.',
        ''
    ]
    return '\n'.join(lines)
