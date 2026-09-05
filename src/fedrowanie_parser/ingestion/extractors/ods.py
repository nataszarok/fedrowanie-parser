from __future__ import annotations
from pathlib import Path
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P
from ..models import CellTable


def _cell_text(cell: TableCell) -> str:
    parts=[]
    for p in cell.getElementsByType(P):
        bits=[]
        for n in p.childNodes:
            data=getattr(n,"data",None)
            if data: bits.append(data)
        parts.append("".join(bits))
    return " ".join(parts).strip()


def extract_ods(path: Path) -> list[CellTable]:
    doc=load(str(path)); out=[]
    for table in doc.spreadsheet.getElementsByType(Table):
        rows=[]
        for tr in table.getElementsByType(TableRow):
            vals=[]
            for c in tr.getElementsByType(TableCell):
                repeat=int(c.getAttribute("numbercolumnsrepeated") or 1)
                val=c.getAttribute("value")
                text=_cell_text(c)
                item=text if text else val
                vals.extend([item]*min(repeat,64))
            while vals and vals[-1] in (None,""): vals.pop()
            if vals and any(v not in (None,"") for v in vals): rows.append(vals)
        if rows: out.append(CellTable(path, table.getAttribute("name") or "sheet", None, rows, "odfpy"))
    return out
