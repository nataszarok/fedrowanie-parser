from __future__ import annotations
from pathlib import Path
import sqlite3,re
from .extractors import extract_tables
from .mapper import map_table
from .institution import institution_from_filename, resolve_institution
from .models import DocumentIngestion
from .storage import replace_document
from .controls import source_controls, compare_controls

SUPPORTED={'.pdf','.xls','.xlsx','.ods','.docx'}

def _document_year_status(path, tables) -> tuple[bool,str]:
    # A letter dated 2026 can legitimately answer a request about salaries paid in
    # 2025.  Reject a document only when 2026 is attached to the *data period*, not
    # merely to correspondence metadata such as the signature/date/reference number.
    text=' '.join(str(c) for t in tables for row in t.rows[:80] for c in row[:16])
    combined=f"{path.name} {text}"
    if re.search(r'(?<!\d)2025(?!\d)',combined):
        return True,'explicit_2025'
    data_2026=re.search(
        r'(?i)(?:dane\s+za|wynagrodzeni\w*\s+(?:za|w)|zarobk\w*\s+(?:za|w)|'
        r'wypłac\w*\s+(?:za|w)|wyplac\w*\s+(?:za|w))[^.;\n]{0,40}(?<!\d)2026(?!\d)',
        combined,
    )
    if data_2026:
        return False,'explicit_data_period_2026'
    return True,'year_inferred_or_correspondence_date_only'

def ingest_file(path: Path, con: sqlite3.Connection|None=None, persist=True) -> DocumentIngestion:
    detected=institution_from_filename(path)
    pk,name=resolve_institution(con,detected)
    try:
        tables=extract_tables(path)
    except Exception as e:
        d=DocumentIngestion(str(path),path.suffix.lower(),name,pk,'ERROR',f'{type(e).__name__}: {e}')
        if con is not None and persist: replace_document(con,d)
        return d
    if not tables:
        d=DocumentIngestion(str(path),path.suffix.lower(),name,pk,'NO_TABLES','no extractable tables')
    else:
        year_ok,year_reason=_document_year_status(path,tables)
        if not year_ok:
            d=DocumentIngestion(str(path),path.suffix.lower(),name,pk,'SKIPPED_YEAR',year_reason,tables_seen=len(tables))
            if con is not None and persist: replace_document(con,d)
            return d
        rows=[]
        for t in tables: rows.extend(map_table(t,name,pk))
        # Cross-extractor dedup (PDF geometry table + text fallback can see same record).
        best={}
        for r in rows:
            key=(re.sub(r'\W+','',r.source_name.casefold()),round(r.gross_compensation or -1,2),round(r.net_compensation or -1,2),r.source_locator.split('/')[0])
            old=best.get(key)
            if old is None or (r.confidence=='wysoka' and old.confidence!='wysoka'): best[key]=r
        rows=list(best.values())
        gross=round(sum(r.gross_compensation or 0 for r in rows),2); net=round(sum(r.net_compensation or 0 for r in rows),2)
        controls=source_controls(tables); check=compare_controls(len(rows),gross,controls)
        status=('NO_ROWS' if not rows else 'CONTROL_MISMATCH' if (check['count_match'] is False or check['gross_match'] is False) else 'OK')
        d=DocumentIngestion(str(path),path.suffix.lower(),name,pk,status,year_reason,len(tables),len(rows),len(rows),gross,net,rows,check['counts'],check['gross_sums'],check['count_match'],check['gross_match'])
    if con is not None and persist: replace_document(con,d)
    return d

def ingest_directory(input_dir: Path, db_path: Path, persist=True) -> list[DocumentIngestion]:
    con=sqlite3.connect(db_path)
    try:
        docs=[]
        for p in sorted(input_dir.rglob('*')):
            if p.is_file() and p.suffix.lower() in SUPPORTED and '__MACOSX' not in p.parts and not p.name.startswith(('._','~$')):
                docs.append(ingest_file(p,con,persist=persist))
        return docs
    finally: con.close()
