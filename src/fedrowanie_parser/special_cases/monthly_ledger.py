
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional

# Generic monthly ledger row:
# | 01.01.2025 | Kowalski Jan | 12 345,67 |
ROW_RE = re.compile(
    r"\|\s*(\d{2}\.\d{2}\.(\d{4}))\s*\|\s*([^|]*)\|\s*"
    r"(-?\d{1,3}(?:[ .]\d{3})*(?:,\d{2})|-?\d+,\d{2})\s*\|"
)

HEADER_RE = re.compile(
    r"(?is)\|\s*Data\s+Dokumentu\s*\|\s*Podmiot\s*\|\s*Warto(?:s|ś)c\s*\|"
)

PROF_PREFIX_RE = re.compile(
    r"(?i)^(?:(?:lek(?:arz)?|dr|prof|mgr)\.?\s*(?:med\.?)?\s+)"
)

BUSINESS_RE = re.compile(
    r"(?i)\b(?:sp\.?\s*z\.?\s*o\.?\s*o\.?|spółka|spolka|s\.?c\.?|"
    r"praktyka|gabinet|fizjoterapia|rehabilitacja|kingmed|medyczn\w*|"
    r"nzoz|zoz|poradnia|centrum)\b"
)

@dataclass
class LedgerTx:
    date: str
    year: int
    entity_raw: str
    entity_key: str
    amount: float
    raw_row: str

@dataclass
class AnnualEntity:
    entity_key: str
    display_name: str
    annual_total: float
    tx_count: int
    months_count: int
    min_tx: float
    max_tx: float
    has_negative_correction: bool
    entity_kind: str

def parse_money_pl(value: str) -> Optional[float]:
    """Parse a Polish-formatted monetary value into a decimal number."""
    s=(value or "").strip().replace("\xa0"," ").replace(" ","")
    s=s.replace(".","").replace(",",".")
    try:
        return round(float(s),2)
    except Exception:
        return None

def clean_entity(value: str) -> str:
    """Normalize a person or entity label extracted from a monthly ledger."""
    s=" ".join((value or "").split()).strip(" \t.,;:|")
    # Strip only a complete professional prefix followed by whitespace.
    # This intentionally does NOT turn "Lekan" into "an".
    s=PROF_PREFIX_RE.sub("",s)
    return " ".join(s.split()).strip(" \t.,;:|")

def canonical_entity(value: str) -> str:
    # Conservative normalization: no fuzzy merge, no diacritic removal.
    # Case and whitespace differences are safe to merge.
    """Return a canonical comparison key for an entity label."""
    s=clean_entity(value)
    return s.casefold()

def display_choice(values: Iterable[str]) -> str:
    """Choose the preferred display form among equivalent entity labels."""
    counts=defaultdict(int)
    original={}
    for v in values:
        c=clean_entity(v)
        counts[c.casefold()]+=1
        original.setdefault(c.casefold(),c)
    if not counts:
        return ""
    key=max(counts,key=lambda k:(counts[k],len(original[k])))
    return original[key]

def classify_entity(name: str) -> str:
    """Classify a ledger entity as a person, organization, or unknown."""
    s=clean_entity(name)
    if not s:
        return "empty"
    if BUSINESS_RE.search(s):
        return "business_or_practice"
    toks=re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźżÀ-ž'’.-]+",s)
    if len(toks)>=2:
        return "person_like"
    if len(toks)==1:
        return "surname_or_unknown"
    return "other"

def parse_monthly_ledger(text: str, target_year: int=2025) -> list[LedgerTx]:
    """Parse monthly ledger rows into normalized salary transactions."""
    if not HEADER_RE.search(text or ""):
        return []
    out=[]
    for m in ROW_RE.finditer(text or ""):
        date,year_s,entity,amount_s=m.groups()
        year=int(year_s)
        if year != target_year:
            continue
        entity=clean_entity(entity)
        if not entity:
            # Monthly page totals/blank recipient rows are deliberately ignored.
            continue
        amount=parse_money_pl(amount_s)
        if amount is None:
            continue
        out.append(LedgerTx(
            date=date,
            year=year,
            entity_raw=entity,
            entity_key=canonical_entity(entity),
            amount=amount,
            raw_row=m.group(0).strip()
        ))
    return out


def _strip_diacritics(s: str) -> str:
    import unicodedata
    x=unicodedata.normalize("NFKD",s or "")
    return "".join(c for c in x if not unicodedata.combining(c))

def _tokenize_person(name: str) -> list[str]:
    s=clean_entity(name)
    return re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźżÀ-ž'’-]+",s)

def _person_similarity(a: str, b: str) -> float:
    aa=" ".join(_tokenize_person(a)).casefold()
    bb=" ".join(_tokenize_person(b)).casefold()
    return SequenceMatcher(None,aa,bb).ratio()

def _safe_same_person(a: AnnualEntity, b: AnnualEntity) -> bool:
    # This helper is used only inside one institution's already-extracted ledger.
    if a.entity_kind not in {"person_like","surname_or_unknown"}:
        return False
    if b.entity_kind not in {"person_like","surname_or_unknown"}:
        return False
    ta=_tokenize_person(a.display_name)
    tb=_tokenize_person(b.display_name)
    if not ta or not tb:
        return False

    na=" ".join(_strip_diacritics(t).casefold() for t in ta)
    nb=" ".join(_strip_diacritics(t).casefold() for t in tb)
    if na==nb:
        return True

    if len(ta)>=2 and len(tb)>=2:
        sa=_strip_diacritics(ta[0]).casefold()
        sb=_strip_diacritics(tb[0]).casefold()
        ga=_strip_diacritics(ta[-1]).casefold()
        gb=_strip_diacritics(tb[-1]).casefold()
        if sa==sb and (ga.startswith(gb) or gb.startswith(ga)) and min(len(ga),len(gb))>=5:
            return True

    sim=_person_similarity(a.display_name,b.display_name)
    if sim>=0.92 and len(ta)==len(tb):
        ea=[_strip_diacritics(x).casefold() for x in ta]
        eb=[_strip_diacritics(x).casefold() for x in tb]
        if sum(x==y for x,y in zip(ea,eb))>=1:
            return True
    return False

def merge_local_person_variants(rows: Iterable[AnnualEntity]) -> list[AnnualEntity]:
    """Merge likely spelling variants of the same person within one institution."""
    rows=list(rows)
    parent=list(range(len(rows)))

    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x

    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb:
            parent[rb]=ra

    for i,a in enumerate(rows):
        for j in range(i+1,len(rows)):
            if _safe_same_person(a,rows[j]):
                union(i,j)

    groups=defaultdict(list)
    for i,r in enumerate(rows):
        groups[find(i)].append(r)

    out=[]
    for items in groups.values():
        if len(items)==1:
            out.append(items[0])
            continue

        def score_name(r):
            name=r.display_name
            diacritics=sum(ch in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ" for ch in name)
            return (diacritics,len(name),r.tx_count)

        display=max(items,key=score_name).display_name
        out.append(AnnualEntity(
            entity_key=canonical_entity(display),
            display_name=display,
            annual_total=round(sum(x.annual_total for x in items),2),
            tx_count=sum(x.tx_count for x in items),
            months_count=max(x.months_count for x in items),
            min_tx=min(x.min_tx for x in items),
            max_tx=max(x.max_tx for x in items),
            has_negative_correction=any(x.has_negative_correction for x in items),
            entity_kind="person_like" if any(x.entity_kind=="person_like" for x in items) else items[0].entity_kind,
        ))
    return sorted(out,key=lambda x:x.annual_total,reverse=True)

def aggregate_transactions(txs: Iterable[LedgerTx]) -> list[AnnualEntity]:
    """Aggregate parsed transactions into annual totals per entity."""
    groups=defaultdict(list)
    for tx in txs:
        groups[tx.entity_key].append(tx)
    out=[]
    for key,items in groups.items():
        vals=[x.amount for x in items]
        months={x.date[3:5] for x in items}
        display=display_choice(x.entity_raw for x in items)
        out.append(AnnualEntity(
            entity_key=key,
            display_name=display,
            annual_total=round(sum(vals),2),
            tx_count=len(items),
            months_count=len(months),
            min_tx=min(vals),
            max_tx=max(vals),
            has_negative_correction=any(v<0 for v in vals),
            entity_kind=classify_entity(display),
        ))
    return sorted(out,key=lambda x:x.annual_total,reverse=True)

def aggregate_monthly_ledger(text: str, target_year: int=2025) -> list[AnnualEntity]:
    """Parse and aggregate a monthly ledger into annual remuneration rows."""
    return aggregate_transactions(parse_monthly_ledger(text,target_year))

def near_duplicate_candidates(rows: Iterable[AnnualEntity], threshold: float=0.90):
    """Diagnostic only. Never merges names automatically."""
    vals=list(rows)
    out=[]
    for i,a in enumerate(vals):
        if len(a.entity_key)<6:
            continue
        for b in vals[i+1:]:
            if len(b.entity_key)<6:
                continue
            score=SequenceMatcher(None,a.entity_key,b.entity_key).ratio()
            if score>=threshold:
                out.append({
                    "score":round(score,4),
                    "name_a":a.display_name,
                    "name_b":b.display_name,
                    "total_a":a.annual_total,
                    "total_b":b.annual_total,
                })
    return sorted(out,key=lambda x:x["score"],reverse=True)

def read_case_text(db_path: str, institution_pk: int) -> tuple[int,str]:
    """Read all source text associated with a case from SQLite."""
    con=sqlite3.connect(db_path)
    con.row_factory=sqlite3.Row
    row=con.execute(
        "SELECT pk FROM cases WHERE institution_pk=? ORDER BY pk LIMIT 1",
        (institution_pk,)
    ).fetchone()
    if not row:
        con.close()
        raise ValueError(f"No case for institution_pk={institution_pk}")
    case_pk=int(row["pk"])
    parts=[
        r["text"] or ""
        for r in con.execute(
            "SELECT text FROM case_pages WHERE case_pk=? ORDER BY rowid",
            (case_pk,)
        )
    ]
    con.close()
    return case_pk,"\n".join(parts)

def write_csv(path: str, rows: Iterable[AnnualEntity]):
    """Write aggregated monthly-ledger rows to CSV."""
    rows=list(rows)
    fields=list(asdict(rows[0]).keys()) if rows else [
        "entity_key","display_name","annual_total","tx_count","months_count",
        "min_tx","max_tx","has_negative_correction","entity_kind"
    ]
    with open(path,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))

def main():
    """Run the standalone monthly-ledger parser CLI."""
    ap=argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--institution-pk",type=int,required=True)
    ap.add_argument("--year",type=int,default=2025)
    ap.add_argument("--out-csv",required=True)
    ap.add_argument("--duplicates-csv")
    args=ap.parse_args()

    case_pk,text=read_case_text(args.db,args.institution_pk)
    txs=parse_monthly_ledger(text,args.year)
    annual=aggregate_transactions(txs)
    write_csv(args.out_csv,annual)

    if args.duplicates_csv:
        dups=near_duplicate_candidates(annual)
        with open(args.duplicates_csv,"w",newline="",encoding="utf-8-sig") as f:
            fields=["score","name_a","name_b","total_a","total_b"]
            w=csv.DictWriter(f,fieldnames=fields,delimiter=";")
            w.writeheader()
            w.writerows(dups)

    print(f"case_pk={case_pk}")
    print(f"transactions={len(txs)}")
    print(f"annual_entities={len(annual)}")
    print(f"annual_sum={sum(x.annual_total for x in annual):.2f}")

if __name__=="__main__":
    main()
