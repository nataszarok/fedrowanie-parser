from __future__ import annotations
from pathlib import Path
from docx import Document
from ..models import CellTable

def extract_docx(path: Path) -> list[CellTable]:
    doc=Document(path); out=[]
    for i,table in enumerate(doc.tables,1):
        rows=[[c.text.strip() for c in r.cells] for r in table.rows]
        rows=[r for r in rows if any(r)]
        if rows: out.append(CellTable(path, f"table-{i}", None, rows, "python-docx"))
    return out
