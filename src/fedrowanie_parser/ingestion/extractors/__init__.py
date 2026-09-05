from pathlib import Path
from .spreadsheet import extract_spreadsheet
from .ods import extract_ods
from .docx import extract_docx
from .pdf import extract_pdf

def extract_tables(path: Path):
    ext=path.suffix.lower()
    if ext in {".xls",".xlsx"}: return extract_spreadsheet(path)
    if ext==".ods": return extract_ods(path)
    if ext==".docx": return extract_docx(path)
    if ext==".pdf": return extract_pdf(path)
    return []

__all__=["extract_tables"]
