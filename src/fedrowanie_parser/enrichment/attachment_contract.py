
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Iterable

ATTACHMENT_RE = re.compile(
    r'(?im)^(?P<name>[^\n]{1,260}\.(?:pdf|xlsx?|xlsm|ods|csv|docx?|rtf|zip|rar|7z))\s*$'
)

CONTRACT_PATTERNS = [
    ("umowa o pracę", re.compile(
        r'(?i)(?:(?:^|[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])uop(?:[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]|$)|'
        r'um[oó]w\w*[\s._-]+o[\s._-]+prac[ęe])')),
    ("umowa zlecenia", re.compile(r'(?i)um[oó]w\w*[\s._-]+zlecen\w*')),
    ("kontrakt/cywilnoprawna", re.compile(
        r'(?i)(?:kontrakt\w*|um[oó]w\w*[\s._-]+cywiln\w*[- _]?prawn\w*|'
        r'cywiln\w*[- _]?prawn\w*|podwykonawst\w*[\s._-]+medyczn\w*)')),
    ("działalność gospodarcza", re.compile(
        r'(?i)dzia[łl]alno[śs][ćc][\s._-]+gospodarcz\w*')),
]

@dataclass
class ContractZone:
    filename: str
    text: str
    start: int
    end: int
    contract_type: str
    source: str
    evidence: str

@dataclass
class AttachmentSection:
    filename: str
    text: str
    start: int
    end: int

def _compact(s) -> str:
    if s is None or (isinstance(s,float) and s!=s):
        s=""
    s=str(s).replace("\xa0"," ")
    s=re.sub(r'[\|\t]+',' ',s)
    s=re.sub(r'\s+',' ',s)
    return s.strip()

def _labels(text: str) -> list[tuple[str,str,int]]:
    hits=[]
    for label,pat in CONTRACT_PATTERNS:
        for m in pat.finditer(text or ""):
            hits.append((label,m.group(0),m.start()))
    return sorted(hits,key=lambda x:x[2])

def _logical_label(hits: list[tuple[str,str,int]]) -> tuple[Optional[str],Optional[str]]:
    labels={x[0] for x in hits}
    if not labels:
        return None,None
    if labels=={"umowa o pracę","umowa zlecenia"}:
        ev=" + ".join(sorted({x[1] for x in hits},key=len)[:2])
        return "umowa o pracę / umowa zlecenia",ev
    if len(labels)==1:
        label=next(iter(labels))
        return label,hits[0][1]
    return None,None

def split_attachments(case_text: str) -> list[AttachmentSection]:
    """Split document text into attachment-scoped text blocks."""
    text=case_text or ""
    ms=list(ATTACHMENT_RE.finditer(text))
    out=[]
    for i,m in enumerate(ms):
        end=ms[i+1].start() if i+1<len(ms) else len(text)
        out.append(AttachmentSection(
            filename=m.group("name").strip(),
            text=text[m.end():end],
            start=m.start(),
            end=end,
        ))
    return out

def _filename_zone(att: AttachmentSection) -> Optional[ContractZone]:
    label,evidence=_logical_label(_labels(att.filename))
    if not label:
        return None
    return ContractZone(
        filename=att.filename,text=att.text,start=0,end=len(att.text),
        contract_type=label,source="filename",evidence=evidence or label
    )

def _heading_like(line: str) -> bool:
    s=_compact(line)
    if not s or len(s)>240:
        return False
    # Strip markdown decoration before structural checks.
    plain=re.sub(r'^[#*_ -]+','',s).strip()
    # A table/data row mentioning "umowa zlecenie" in notes is not a heading.
    if re.match(r'^\d+\b',plain):
        return False
    letters=[c for c in plain if c.isalpha()]
    upper_ratio=(sum(c.isupper() for c in letters)/len(letters)) if letters else 0
    return (
        s.lstrip().startswith("#")
        or (upper_ratio>=0.72 and len(plain)<=180)
        or bool(re.match(
            r'(?i)^(?:zestawienie\b|wynagrodzeni\w*\s+(?:wypłacone|lekarz|za)|'
            r'umow\w*\s+o\s+prac|umow\w*\s+zlecen|kontrakt\w*)',
            plain
        ))
    )

def _local_heading_zones(att: AttachmentSection) -> list[ContractZone]:
    # Preserve line offsets.
    anchors=[]
    pos=0
    for line in att.text.splitlines(True):
        clean=line.rstrip("\r\n")
        hits=_labels(clean)
        label,evidence=_logical_label(hits)
        if label and _heading_like(clean):
            anchors.append((pos,label,evidence or _compact(clean),_compact(clean)))
        pos+=len(line)

    # Remove near-duplicate anchors for same type that occur in boilerplate.
    filtered=[]
    for a in anchors:
        if filtered and a[1]==filtered[-1][1] and a[0]-filtered[-1][0]<250:
            continue
        filtered.append(a)
    anchors=filtered

    zones=[]
    for i,(start,label,evidence,line) in enumerate(anchors):
        end=anchors[i+1][0] if i+1<len(anchors) else len(att.text)
        # Require enough content after heading to contain actual rows.
        if end-start<80:
            continue
        zones.append(ContractZone(
            filename=att.filename,
            text=att.text[start:end],
            start=start,end=end,
            contract_type=label,source="local_header",evidence=line[:180]
        ))
    return zones

def _numbered_ad_zones(att: AttachmentSection) -> list[ContractZone]:
    # Generic pattern:
    # 1) ... kontrakty ...
    # 2) ... umowy o pracę i zlecenia ...
    # then "# Ad. 1", "# Ad. 2".
    intro=att.text[:5000]
    desc={}
    for m in re.finditer(r'(?is)(?<!\d)([1-9])\)\s*(.{1,700}?)(?=(?:\s+[1-9]\)|#\s*Ad\.|\Z))',intro):
        n=int(m.group(1))
        label,evidence=_logical_label(_labels(m.group(2)))
        if label:
            desc[n]=(label,evidence or _compact(m.group(2))[:150])

    ads=[]
    for m in re.finditer(r'(?im)^\s*[*#_ -]*Ad\.?\s*([1-9])\b[^\n]*$',att.text):
        n=int(m.group(1))
        if n in desc:
            ads.append((m.start(),n))
    if not ads:
        return []

    zones=[]
    for i,(start,n) in enumerate(ads):
        end=ads[i+1][0] if i+1<len(ads) else len(att.text)
        label,evidence=desc[n]
        zone_text=att.text[start:end]
        # The actual table heading after "Ad. N" can be more precise than the
        # introductory description (and can correct OCR typos in the intro).
        head_label,head_evidence=_logical_label(_labels(zone_text[:1600]))
        if head_label:
            label=head_label
            evidence=head_evidence or evidence
        zones.append(ContractZone(
            filename=att.filename,text=zone_text,
            start=start,end=end,contract_type=label,
            source="numbered_section",evidence=f"Ad. {n}: {evidence}"
        ))
    return zones

def _homogeneous_zone(att: AttachmentSection) -> Optional[ContractZone]:
    hits=_labels(att.text)
    label,evidence=_logical_label(hits)
    if not label:
        return None
    # Only accept an attachment-wide inference when contract language is genuinely
    # homogeneous throughout the whole attachment.
    return ContractZone(
        filename=att.filename,text=att.text,start=0,end=len(att.text),
        contract_type=label,source="homogeneous_attachment",evidence=evidence or label
    )

def contract_zones(case_text: str) -> list[ContractZone]:
    """Identify attachment regions associated with explicit contract types."""
    out=[]
    for att in split_attachments(case_text):
        fz=_filename_zone(att)
        if fz:
            out.append(fz)
            continue

        numbered=_numbered_ad_zones(att)
        local=_local_heading_zones(att)

        if numbered:
            out.extend(numbered)
        if local:
            out.extend(local)

        # Only use whole attachment if no scoped zones exist and the entire
        # attachment contains one logical type.
        if not numbered and not local:
            hz=_homogeneous_zone(att)
            if hz:
                out.append(hz)
    return out

def _money_key(v) -> Optional[int]:
    if v is None or (isinstance(v,float) and v!=v):
        return None
    try: return int(round(float(v)*100))
    except Exception: return None

def _money_keys(text: str) -> set[int]:
    out=set()
    for m in re.finditer(r'(?<!\d)-?\d{1,3}(?:[ .]\d{3})*[,.]\d{2}(?!\d)',text or ""):
        s=m.group(0).replace(" ","").replace(".","").replace(",",".")
        try: out.add(int(round(float(s)*100)))
        except Exception: pass
    return out

def _meaningful_name(name) -> Optional[str]:
    s=_compact(name)
    if not s: return None
    if re.fullmatch(r'(?i)Lekarz(?:\s+(?:nr\s*)?\d+)?',s): return None
    return s

def match_row_to_zone(*,raw_row,name,gross,net,zones:Iterable[ContractZone]):
    """Match a salary row to the attachment contract zone containing it."""
    raw=_compact(raw_row)
    nm=_meaningful_name(name)
    gk,nk=_money_key(gross),_money_key(net)
    candidates=[]

    for z in zones:
        compact=_compact(z.text)
        monies=_money_keys(z.text)
        score=0; reasons=[]
        if raw and len(raw)>=8 and raw in compact:
            score+=100; reasons.append("raw_row")
        if nm and nm.casefold() in compact.casefold():
            score+=25; reasons.append("name")
        if gk is not None and gk in monies:
            score+=20; reasons.append("gross")
        if nk is not None and nk in monies:
            score+=20; reasons.append("net")
        if score:
            candidates.append((score,z,reasons))

    if not candidates:
        return None
    # Provenance must be exact: only a zone containing this record's normalized
    # raw_row may provide its contract type.
    candidates=[x for x in candidates if "raw_row" in x[2]]
    if not candidates:
        return None
    candidates.sort(key=lambda x:x[0],reverse=True)
    best_score,best,best_reasons=candidates[0]
    tied=[x for x in candidates if x[0]==best_score]
    if len({x[1].contract_type for x in tied})>1:
        return None

    return {
        "contract_type":best.contract_type,
        "source":best.source,
        "filename":best.filename,
        "evidence":best.evidence,
        "score":best_score,
        "match_reasons":",".join(best_reasons),
    }

def fill_missing_contracts_for_case(case_text: str, rows: list[dict]) -> list[dict]:
    """Fill missing contract types using attachment-level context."""
    zones=contract_zones(case_text)
    out=[]
    for row in rows:
        current=row.get("typ umowy")
        if current is None or (isinstance(current,float) and current!=current):
            current=""
        current=str(current).strip()
        r=dict(row)
        if current:
            out.append(r); continue

        match=match_row_to_zone(
            raw_row=row.get("raw_row"),
            name=row.get("Nazwa"),
            gross=row.get("wynagrodzenie brutto"),
            net=row.get("wynagrodzenie netto"),
            zones=zones,
        )
        if match:
            r["typ umowy"]=match["contract_type"]
            comment=r.get("komentarz")
            if comment is None or (isinstance(comment,float) and comment!=comment):
                comment=""
            extra=(
                f"typ umowy z kontekstu załącznika: {match['filename']} "
                f"({match['source']}; {match['evidence']}; match={match['match_reasons']})"
            )
            r["komentarz"]=(str(comment).strip()+"; "+extra).strip("; ")
        out.append(r)
    return out
