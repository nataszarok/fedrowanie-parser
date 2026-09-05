from __future__ import annotations
import re
from .models import CellTable, IngestedSalary
from .money import parse_money
from ..enrichment.person_name import norm
from ..enrichment.doctor_initials import normalize_initials
from .person import person_from_source
from .text_records import parse_salary_text_line

YEAR_RE=re.compile(r'(?<!\d)2025(?!\d)')
SUMMARY_RE=re.compile(r'(?i)\b(?:suma|razem|średnia|srednia|mediana|max(?:imum)?|minimum|count|liczba|podsuma)\b')
AMOUNT_RE=re.compile(r'(?i)(?:wynagrodz|kwot|brutto|netto|wartość|wartosc|wypłac|wyplac)')
NAME_RE=re.compile(r'(?i)(?:nazwisko|imię|imie|nazwa|lekarz|identyfikator|nr ewidencyjny|kod|dane osobowe)')
GROSS_RE=re.compile(r'(?i)brutto')
NET_RE=re.compile(r'(?i)netto')
CONTRACT_RE=re.compile(r'(?i)(umowa o prac|uop|kontrakt|cywilno|zlecen|świadcze|swiadcze)')
ANON_RE=re.compile(r'(?i)^(?:lekarz\s*\d+|xx\d+xx|[A-Z]?\d{3,}|K\d{3,})$')
NUMERIC_ID_RE=re.compile(r'^\d{1,8}$')
BAD_PERSON_RE=re.compile(r'(?i)\b(?:lekarz|specjalista|stanowisko|asystent|ordynator|rezydent|wynagrodzenie)\b')

def _txt(x): return norm(x)

_INITIALS_PAIR_RE = re.compile(r"(?i)^[A-ZĄĆĘŁŃÓŚŹŻ]\.?\s+[A-ZĄĆĘŁŃÓŚŹŻ]\.?$")
_PLACEHOLDER_RE = re.compile(r"(?i)^x{2,}(?:\s+x{2,})+$")

def _initials_from_source(value: str) -> str | None:
    value=_txt(value)
    if not value or _PLACEHOLDER_RE.fullmatch(value):
        return None
    if _INITIALS_PAIR_RE.fullmatch(value):
        return normalize_initials(value)
    compact=re.sub(r'\s+','',value)
    if re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ]\.?[A-ZĄĆĘŁŃÓŚŹŻ]\.?',compact,re.I):
        return normalize_initials(compact)
    return None

def _is_numeric_cell(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool): return True
    text=_txt(value)
    return bool(re.fullmatch(r"-?\d{1,3}(?:[ \u00a0.]\d{3})*(?:,\d{1,2})?|-?\d+(?:[.,]\d{1,2})?", text))

def _money_cell_value(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool): return float(value)
    text=_txt(value)
    if not re.fullmatch(r"-?\d{1,3}(?:[ \u00a0.]\d{3})*(?:,\d{1,2})?\s*(?:zł)?|-?\d+(?:[.,]\d{1,2})?\s*(?:zł)?", text, re.I):
        return None
    return parse_money(text)

def _header_candidates(rows):
    scored=[]
    for i,row in enumerate(rows[:15]):
        text=' | '.join(_txt(c) for c in row)
        nonempty=sum(bool(_txt(c)) for c in row)
        numeric=sum(_is_numeric_cell(c) for c in row[:6])
        score=3*bool(AMOUNT_RE.search(text))+2*bool(NAME_RE.search(text))+bool(CONTRACT_RE.search(text))+bool(YEAR_RE.search(text))
        if nonempty == 1: score -= 3
        if numeric >= 1: score -= 6
        if nonempty >= 2: score += 1
        scored.append((score,i))
    return sorted(scored, reverse=True)

def _merged_headers(rows, idx, width):
    # Combine adjacent structural header rows, but never smear a one-cell title
    # across the first data/id column.
    start=max(0,idx-2)
    header_rows=[]
    for r in rows[start:idx+1]:
        nonempty=sum(bool(_txt(c)) for c in r)
        numeric=sum(_is_numeric_cell(c) for c in r[:6])
        if nonempty >= 2 and numeric == 0:
            header_rows.append(r)
    if not header_rows:
        if sum(bool(_txt(c)) for c in rows[idx]) < 2:
            return ['']*width
        header_rows=[rows[idx]]
    out=[]
    for c in range(width):
        vals=[]
        for r in header_rows:
            if c<len(r):
                s=_txt(r[c])
                if s and s not in vals: vals.append(s)
        out.append(' '.join(vals))
    return out

def _person_from_cells(cells, name_cols):
    parts=[]
    for i in name_cols:
        if i<len(cells):
            s=_txt(cells[i])
            if s: parts.append(s)
    candidate=' '.join(parts).strip()
    if not candidate: return '', ''
    return candidate, person_from_source(candidate)

def _line_rows(table, institution_name, institution_pk):
    out=[]
    money_pat=r"-?\d{1,3}(?:[ \u00a0.]\d{3})*(?:,\d{2})|-?\d+(?:[.,]\d{2})"
    for ri,row in enumerate(table.rows,1):
        line=_txt(row[0] if row else '')
        if not line or SUMMARY_RE.search(line): continue

        # Structured prose list: `1) Practice / doctor – 123.456,78 zł brutto`.
        parsed=parse_salary_text_line(line)
        if parsed is not None and parsed.numbered:
            source=parsed.source_name; amount=parsed.amount
            gross=amount if parsed.kind!='net' else None
            net=amount if parsed.kind=='net' else None
            doctor=person_from_source(source)
            out.append(IngestedSalary(
                str(table.source_file),f"p.{table.page or 0}/line {ri}",institution_name,institution_pk,
                source,doctor or None,doctor_initials=_initials_from_source(source),recipient_type="doctor" if doctor else "anonymous_doctor",
                net_compensation=net,gross_compensation=gross,raw_row=line,
                parser='generic-numbered-text-list',
                confidence='wysoka' if parsed.kind in {'gross','net'} else 'średnia',
                comment=f"numbered text salary record; amount kind={parsed.kind}"
            ))
            continue

        # Preserve the previous generic PDF-line behaviour for already supported files.
        m=re.fullmatch(rf"(?i)lekarz\s*(\d{{1,4}})\s+({money_pat})\s*(?:zł)?", line)
        if m:
            source=f"Lekarz {m.group(1)}"; amount=parse_money(m.group(2))
        else:
            m=re.fullmatch(rf"(\d{{1,4}})[.)]?\s+({money_pat})\s*(?:zł)?", line)
            if m:
                source=f"Lekarz {m.group(1)}"; amount=parse_money(m.group(2))
            else:
                mm=re.search(rf"({money_pat})\s*(?:zł)?\s*$", line, re.I)
                if mm:
                    source=_txt(line[:mm.start()]).strip('|;-')
                    amount=parse_money(mm.group(1))
                else:
                    # OCR tables often leave `|`, `]`, `)` after the amount or a
                    # space before the decimal comma.  Accept that damage only if
                    # the left side looks like initials or an actual person's name.
                    tolerant=re.sub(r'(?<=\d)\s+([,.])',r'\1',line)
                    tr=parse_salary_text_line(tolerant)
                    if tr is None: continue
                    source=tr.source_name; amount=tr.amount
                    compact=re.sub(r'[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9.-]','',source)
                    initials=bool(re.fullmatch(r'(?:[A-Za-zĄĆĘŁŃÓŚŹŻ][._-]?){2,4}\d?',compact))
                    if not initials and not person_from_source(source):
                        continue
        if amount is None or amount<100: continue
        if not source or source in {'za rok','rok'} or re.fullmatch(r'(?i)(?:w )?2025',source): continue
        if len(source)>160 or re.search(r'(?i)\b(?:telefon|regon|nip|kapitał|data|wniosek|pytania na temat)\b',source): continue
        doctor=person_from_source(source)
        out.append(IngestedSalary(str(table.source_file),f"p.{table.page or 0}/line {ri}",institution_name,institution_pk,source,doctor or None,doctor_initials=_initials_from_source(source),recipient_type="doctor" if doctor else "anonymous_doctor",gross_compensation=amount,raw_row=line,parser='generic-pdf-line',confidence='średnia',comment='PDF/OCR text-line fallback; amount treated as gross/total unless source distinguishes otherwise'))
    return out

def map_table(table: CellTable, institution_name: str, institution_pk: int|None) -> list[IngestedSalary]:
    if not table.rows: return []
    if table.extractor in {'pymupdf-text','tesseract-text'}: return _line_rows(table,institution_name,institution_pk)
    table_text=' '.join(_txt(c) for row in table.rows[:12] for c in row)
    if re.search(r'(?i)przedzia[łl].*wynagrodz|[śs]rednie wynagrodzenie.*przedzia[łl]', table_text): return []
    width=max(len(r) for r in table.rows)
    scored=_header_candidates(table.rows)
    if scored and scored[0][0]>=3:
        _,hi=scored[0]
        headers=_merged_headers(table.rows,hi,width)
    else:
        # Headerless continuation pages/tables are common in PDF and legacy XLS.
        # Allow them only when a stable high-value numeric column is visible.
        hi=-1
        headers=['']*width
    amount_cols=[i for i,h in enumerate(headers) if AMOUNT_RE.search(h)]
    if not amount_cols:
        # Infer columns by dense high-value numeric cells. Stop before side-panel
        # spreadsheet diagnostics such as count/max/avg/suma.
        from statistics import median
        analytic_start=width
        for c in range(width):
            labels=' '.join(_txt(r[c]) for r in table.rows[:12] if c<len(r))
            if re.search(r'(?i)\b(?:count|max|avg|mediana|suma)\b', labels):
                analytic_start=min(analytic_start,c)
        for c in range(analytic_start):
            sample=[_money_cell_value(r[c]) if c<len(r) else None for r in table.rows[hi+1:hi+15]]
            vals=[x for x in sample if x is not None and abs(x)>=100]
            if len(vals)>=3 and median(abs(x) for x in vals)>=1000:
                amount_cols.append(c)
    strong_name_cols=[i for i,h in enumerate(headers) if re.search(r'(?i)nazwisko|imię|imie|nazwa',h) and i not in amount_cols]
    name_cols=strong_name_cols or [i for i,h in enumerate(headers) if NAME_RE.search(h) and i not in amount_cols]
    if not name_cols:
        name_cols=[i for i in range(min(width,3)) if i not in amount_cols]
    out=[]
    for ri,cells in enumerate(table.rows[hi+1:],hi+2):
        rowtext=' | '.join(_txt(x) for x in cells)
        lead=' | '.join(_txt(x) for x in cells[:max(3, min(len(cells),4))])
        if not rowtext or re.match(r'(?i)^\s*(?:suma|razem|średnia|srednia|mediana|max(?:imum)?|minimum|count|liczba)\b', lead): continue
        source,doctor=_person_from_cells(cells,name_cols)
        if not source: source=f"Lekarz {ri-hi-1}"
        amounts=[]
        for c in amount_cols:
            if c>=len(cells): continue
            v=parse_money(cells[c])
            if v is None or v<100: continue
            # Dense OCR can attach a small page/header artefact to a title.
            # Keep real first salary rows even when the title was merged into
            # their label, but discard implausibly small title-only artefacts.
            if v < 1000 and re.search(r'(?i)^(?:zatrudnienie\b|umowy?\s+cywilno|łączne?\s+(?:wynagrodzenie|wartość)|laczne?\s+(?:wynagrodzenie|wartosc)|funkcja\s+publiczna\b)', source):
                continue
            h=headers[c]
            # avoid spreadsheet analytics accidentally to the right of real table
            if re.search(r'(?i)\b(?:count|max|avg|suma|mediana)\b',h): continue
            amounts.append((c,h,v))
        if not amounts: continue
        # If duplicated cells carry exactly the same gross/net text, emit once per semantic kind.
        seen=set()
        for c,h,v in amounts:
            kind='net' if NET_RE.search(h) and not GROSS_RE.search(h) else 'gross'
            key=(kind,round(v,2))
            if key in seen: continue
            seen.add(key)
            ct=''
            cm=CONTRACT_RE.search(h)
            if cm: ct=cm.group(0)
            gross=v if kind=='gross' else None; net=v if kind=='net' else None
            # Unqualified salary columns are stored as gross/total to match existing schema convention.
            confidence='wysoka' if (GROSS_RE.search(h) or NET_RE.search(h) or YEAR_RE.search(h)) else 'średnia'
            anon=not doctor
            out.append(IngestedSalary(str(table.source_file),f"{table.sheet}:row {ri}",institution_name,institution_pk,source,doctor or None,doctor_initials=_initials_from_source(source),recipient_type="doctor" if doctor else "anonymous_doctor",contract_type=ct or None,net_compensation=net,gross_compensation=gross,raw_row=rowtext,parser=f"generic-{table.extractor}",confidence=confidence,comment=f"mapped from column: {h}"))
    return out
