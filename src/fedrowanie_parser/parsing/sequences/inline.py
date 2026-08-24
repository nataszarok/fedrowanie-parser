"""Inline parser family."""
from __future__ import annotations

from typing import Optional

from ...models import SalaryRow
from ...processing.normalization import *
from ...processing.document import is_metadata_context

__all__ = [
    "parse_numbered_named_inline_salary",
    "parse_lekarz_inline_salary",
    "parse_embedded_numbered_salary_list",
    "parse_specialty_amount_lines",
    "parse_explicit_annual_prose_salary",
    "parse_body_lekarz_number_amount",
    "parse_body_lp_amount",
    "parse_annual_amount_contract_lines",
    "parse_contract_practice_cost_list",
    "parse_single_anonymized_annual_amount",
    "parse_annual_named_colon_amount_list",
]


def parse_numbered_named_inline_salary(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_numbered_named_inline_salary` layout/stage."""
    out = []
    for line in page.splitlines():
        raw = norm_space(line)
        if '|' in raw:
            continue
        if re.search('\\d+-\\d{3},\\d{2}\\b', raw):
            continue
        m = re.match('^(\\d{1,4})[.)]\\s*(.+?)(?:\\s*[—–-]\\s*|\\s+)(\\d[\\d .]*,\\d{2})\\s*(?:(?:zł|zl|z)(?:\\s*brutto)?)?[,.]?$', raw, re.I)
        if not m:
            continue
        val = parse_money(m.group(3))
        if val is None or val <= 0:
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, norm_space(m.group(2)), '', '', None, val, page_no, 'numbered-named-inline', 'wysoka', raw))
    return out if len(out) >= 3 else []

def parse_lekarz_inline_salary(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_lekarz_inline_salary` layout/stage."""
    out = []
    for line in page.splitlines():
        raw = norm_space(line)
        m = re.match('(?i)^lekarz\\s+(\\d{1,4})\\s+(\\d{1,3}(?:[ .]\\d{3})*(?:,\\d{1,2}))\\s+(.+)$', raw)
        if not m:
            continue
        val = parse_money(m.group(2))
        if val is None or val <= 0:
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {m.group(1)}', norm_space(m.group(3)), '', None, val, page_no, 'lekarz-inline-specialty', 'wysoka', raw))
    return out if len(out) >= 3 else []

def parse_embedded_numbered_salary_list(case_pk, institution_pk, placowka, page_no, page, full_doc=''):
    """Parse or process the `parse_embedded_numbered_salary_list` layout/stage."""
    context = full_doc or page
    if not re.search('(?i)wynagrod', context) or '2025' not in context:
        return []
    text = re.sub(',\\s+(?=\\d{1,2}\\b)', ',', norm_space(page))
    pat = re.compile('(?<!\\d)(\\d{1,3})[.)]\\s+(.{1,180}?)\\s*[-–—]\\s*(\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})\\s*(?:zł|zl|zlt|zhl|zt)\\b', re.I)
    med = re.compile('(?i)lekarz|chirurg|psychiatr|stomatolog|okulist|radiolog|anestezj|ordynator|asystent|rehabilitant|urolog|neurolog|kardiolog|internist|laryngolog|gastrolog|epidemiolog|ortoped|ginekolog|pediatr|endokrynolog|diabetolog|dyrektor szpitala|dyżury lekarskie|dyzury lekarskie')
    out = []
    for m in pat.finditer(text):
        label = norm_space(m.group(2))
        if not med.search(label):
            continue
        am = re.search('(\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})', m.group(0))
        if not am:
            continue
        val = parse_money(am.group(0))
        if val is None or val <= 0:
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {m.group(1)}', label, '', None, val, page_no, 'embedded-numbered-salary-list', 'wysoka', norm_space(m.group(0))))
    explicit = bool(re.search('(?i)poniżej przedstawiam listę|ponizej przedstawiam liste', page))
    return out if len(out) >= 5 or (explicit and len(out) >= 3) else []

def parse_specialty_amount_lines(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_specialty_amount_lines` layout/stage."""
    annual_ctx=bool(
        re.search(r'(?is)zestawienie\s+wynagrodze[nń]',page)
        or re.search(r'(?is)wynagrodzenia.{0,220}(?:podziale|stanowisk).{0,220}2025',page)
        or re.search(r'(?is)2025.{0,220}wynagrodzenia.{0,220}(?:stanowisk|podziale)',page)
    )
    if not annual_ctx:
        return []
    # If this is a prose list introduced by "kształtowały się następująco",
    # parse only that list, not a later unrelated salary fact.
    scope=page
    intro=re.search(r'(?is)wynagrodzenia.{0,220}kształtowały\s+się\s+następująco\s*:',page)
    if intro:
        scope=page[intro.end():]
        scope=re.split(r'(?is)\bJednocześnie\s+informuję\b|\bZ\s+poważaniem\b|\bKlauzula\s+informacyjna\b',scope,maxsplit=1)[0]
    out=[]
    med=re.compile(r'(?i)ordynator|chirurg|psychiatr|stomatolog|okulist|lekarz|anestezj|rehabilitant|radiolog|urolog|neurolog|kardiolog|pulm|laryng|asystent|kierownik|dyrektor')
    for line in scope.splitlines():
        raw=norm_space(line).replace('|ekarz','lekarz')
        raw=re.sub(r'^[|+*_\-\s]+','',raw)
        if re.match(r'(?i)^ekarz\b',raw):
            raw='l'+raw
        if not med.search(raw): continue
        m=re.match(
            r'^(.{2,110}?)[-–—]\s*'
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\s*\d{1,2})?\s*(?:zł|zl|zlt|zhl|zt)?[,.]?$',
            raw,re.I
        )
        if not m: continue
        am=re.search(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\s*\d{1,2})?',raw)
        if not am: continue
        val=parse_money(re.sub(r',\s+',',',am.group(0)))
        if val is None or val<=0: continue
        spec=norm_space(m.group(1)).strip(' -–—_+*|')
        out.append(SalaryRow(
            case_pk,institution_pk,placowka,f'Lekarz {len(out)+1}',spec,'',
            None,val,page_no,'specialty-amount-lines','wysoka',raw
        ))
    return out if len(out)>=5 else []

def parse_explicit_annual_prose_salary(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_explicit_annual_prose_salary` layout/stage."""
    has_numbered_context=bool(re.search(r'(?is)zestawienie.{0,100}wynagrodze[nń].{0,100}2025', page))
    has_single_explicit=bool(re.search(
        r'(?is)łączne\s+wynagrodzenie\s+wypłacone\s+.{3,140}?\s+w\s+2025\s+roku\s+wyniosło\s+'
        r'\d{1,3}(?:[ .]\d{3})+',
        page
    ))
    if not (has_numbered_context or has_single_explicit):
        return []

    out=[]
    if has_numbered_context:
        text=re.sub(r'\s+',' ',page)
        marks=list(re.finditer(r'(?<!\d)(\d{1,3})[.)]\s+',text))
        for k,m in enumerate(marks):
            end=marks[k+1].start() if k+1<len(marks) else len(text)
            chunk=text[m.end():end]
            if len(chunk)>500: continue
            wm=re.search(r'(?i)wynagrodzenie\s+brutto\s*:\s*(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})',chunk)
            if wm:
                token=re.search(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})',wm.group(0)).group(0)
                label=chunk[:wm.start()].strip(' ,;-—')
            else:
                am=list(re.finditer(r'(?<!\d)(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})(?:\s*zł)?',chunk,re.I))
                if not am: continue
                token=am[-1].group(0); label=chunk[:am[-1].start()].strip(' ,;-—')
            if not re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]',label): continue
            if re.search(r'(?i)art\.|ust\.|telefon|adres|data:',label): continue
            val=parse_money(token)
            if val is None or val<=0: continue
            out.append(SalaryRow(case_pk,institution_pk,placowka,norm_space(label[:140]),'','',
                                 None,val,page_no,'explicit-annual-prose-salary','wysoka',
                                 f'{m.group(1)} | {norm_space(chunk[:220])}'))
        if len(out)>=3: return out

    m=re.search(
        r'(?is)łączne\s+wynagrodzenie\s+wypłacone\s+(.{3,140}?)\s+w\s+2025\s+roku\s+wyniosło\s+'
        r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:[,.](\d{2}))?\s*zł',
        page
    )
    if m:
        token=m.group(2)+((','+m.group(3)) if m.group(3) else '')
        val=parse_money(token); label=norm_space(m.group(1)).strip(' .,:;-')
        if val is not None and val>0 and re.search(r'(?i)lekarz|dyrektor|ordynator|kierownik',label):
            return [SalaryRow(case_pk,institution_pk,placowka,label,'','',None,val,page_no,
                              'explicit-annual-prose-salary','wysoka',norm_space(m.group(0)))]
    return []

def parse_body_lekarz_number_amount(case_pk, institution_pk, placowka, page_no, page):
    """
    Roczne listy lekarzy w body/OCR:
      Lekarz 1 - 35042 zł
      Lekarz nr 3 952 736,62 zł
      LEKARZ (1) / 13 112,63
      Lekarz Jan Kowalski 697 941,71 zł
      Lekarz 1 / - / 931 818,70 zł brutto
    """
    if not re.search(r'(?is)(?:wynagrodze[nń]|zarobk).{0,260}2025|2025.{0,260}(?:wynagrodze[nń]|zarobk)', page):
        return []
    out=[]; seen=set()
    raw_lines=page.splitlines()
    lines=[norm_space(x) for x in raw_lines if norm_space(x)]

    def add(name,val,raw,kind='brutto'):
        if val is None or val<=0: return
        key=(norm_space(name).lower(),round(val,2))
        if key in seen: return
        seen.add(key)
        out.append(SalaryRow(
            case_pk,institution_pk,placowka,norm_space(name),"","",
            val if kind=='netto' else None,
            None if kind=='netto' else val,
            page_no,"body-lekarz-number-amount","wysoka",raw
        ))

    # One-line rows.
    pat=re.compile(
        r'(?i)^Lekarz\s*'
        r'(?:(?:nr\s*)?\(?(\d{1,4})\)?|([A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż .\-]{2,90}))'
        r'\s*[-–—:]?\s*'
        r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:[,.](\d{2}))?'
        r'\s*(?:zł)?\s*(?:brutto|netto)?[.,]?$'
    )
    for raw in lines:
        m=pat.match(raw)
        if not m: continue
        token=m.group(3)+((','+m.group(4)) if m.group(4) else '')
        val=parse_money(token)
        name=f'Lekarz {m.group(1)}' if m.group(1) else 'Lekarz '+norm_space(m.group(2)).strip(' .:-')
        add(name,val,raw,'netto' if re.search(r'(?i)\bnetto\b',raw) else 'brutto')

    # Vertical rows: Lekarz N / optional "-" / amount.
    i=0
    while i<len(lines)-1:
        lm=re.fullmatch(r'(?i)Lekarz\s*(?:nr\s*)?\(?(\d{1,4})\)?',lines[i])
        if not lm:
            i+=1; continue
        j=i+1
        if j<len(lines) and re.fullmatch(r'[-–—]',lines[j]): j+=1
        if j>=len(lines): break
        am=re.fullmatch(
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:[,.](\d{2}))?\s*(?:zł)?\s*(?:brutto|netto)?[.,]?',
            lines[j],re.I
        )
        if am:
            token=am.group(1)+((','+am.group(2)) if am.group(2) else '')
            add(f'Lekarz {lm.group(1)}',parse_money(token),f'{lines[i]} | {lines[j]}',
                'netto' if re.search(r'(?i)\bnetto\b',lines[j]) else 'brutto')
            i=j+1; continue
        i+=1

    # If this is clearly a mixed anonymous list, include one named public-function row.
    if len(out)>=2:
        for i in range(len(lines)-2):
            nm=lines[i]
            if not re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\-]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\-]+){1,3}',nm):
                continue
            j=i+1
            if re.fullmatch(r'[-–—]',lines[j]):
                j+=1
            if j>=len(lines): continue
            am=re.fullmatch(
                r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:[,.](\d{2}))?\s*(?:zł)?\s*(?:brutto|netto)?[.,]?',
                lines[j],re.I
            )
            if not am: continue
            # avoid headings and signatures
            if re.search(r'(?i)dyrektor|ordynator|kierownik|wynagrodz|lekarz|watchdog|sieć obywatelska',nm):
                continue
            token=am.group(1)+((','+am.group(2)) if am.group(2) else '')
            add(nm,parse_money(token),f'{nm} | {lines[j]}',
                'netto' if re.search(r'(?i)\bnetto\b',lines[j]) else 'brutto')
            break
    return out if len(out)>=2 else []

def parse_body_lp_amount(case_pk, institution_pk, placowka, page_no, page):
    """
    Treść maila:
      LP 1 kwota za 2025 rok - 299.437,92
      LP 2 ... - 181.292,96
    """
    if not re.search(r'(?i)2025', page):
        return []
    out=[]
    for line in page.splitlines():
        raw=norm_space(line)
        m=re.match(
            r'(?i)^LP\.?\s*(\d{1,4})\b.{0,80}?'
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:[,.](\d{2}))?\s*(?:zł)?[.]?$',
            raw
        )
        if not m:
            continue
        token=m.group(2)
        if m.group(3):
            token += ',' + m.group(3)
        val=parse_money(token)
        if val is None or val<=0:
            continue
        out.append(SalaryRow(
            case_pk,institution_pk,placowka,f"Lekarz {m.group(1)}","","",
            None,val,page_no,"body-lp-amount","wysoka",raw
        ))
    return out if len(out)>=2 else []

def parse_annual_amount_contract_lines(case_pk, institution_pk, placowka, page_no, page):
    """Annual anonymous list: one salary amount and contract type on each line."""
    if not (re.search(r'(?i)wynagrodzenia\s+lekarzy\s+za\s+rok\s+2025', page)
            and re.search(r'(?i)bez\s+imion\s+i\s+nazwisk|bez\s+.*nazwisk', page)):
        return []
    candidates=[]
    for raw in page.splitlines():
        vals=money_values(raw)
        ct=detect_contract(raw, '')
        if len(vals)==1 and ct and re.search(r'(?i)umow|kontrakt|cywilnopraw',raw) and not is_metadata_context(raw):
            candidates.append((raw,vals[0],ct))
    if len(candidates)<3: return []
    return [SalaryRow(case_pk,institution_pk,placowka,f'Lekarz {i}','','' if not ct else ct,None,val,page_no,
                      'annual-amount-contract-lines','wysoka',norm_space(raw))
            for i,(raw,val,ct) in enumerate(candidates,1)]

def parse_contract_practice_cost_list(case_pk, institution_pk, placowka, page_no, page):
    """Prose list introduced as N doctors on contracts and their 2025 cost."""
    m=re.search(r'(?is)na\s+kontraktach\s+zatrudnionych\s+by[łl]o\s+(\w+|\d+)\s+lekarzy.{0,220}?koszt.{0,120}?2025.{0,180}?nast[eę]puj[aą]co\s*:',page)
    if not m: return []
    block=page[m.end():]
    block=re.split(r'(?i)\bDYREKTOR\b|\bZ\s+poważaniem\b',block,maxsplit=1)[0]
    out=[]
    # each item ends in an amount; label can include practice/address/NIP, retained as source identity
    block=re.sub(r'\n(?!\s*-)', ' ', block)
    pat=re.compile(r'(?m)^\s*-\s*(.+?)\s*[—–-]\s*(\d{1,3}(?:[ .]\d{3})+(?:[,.]\d{2})\s*zł)\s*$')
    for mm in pat.finditer(block):
        label=norm_space(mm.group(1)); val=parse_money(mm.group(2))
        if val and val>=1000:
            out.append(SalaryRow(case_pk,institution_pk,placowka,label,'','kontrakt/cywilnoprawna',None,val,page_no,
                                 'contract-practice-cost-list','wysoka',norm_space(mm.group(0))))
    return out if len(out)>=2 else []

def parse_single_anonymized_annual_amount(case_pk, institution_pk, placowka, page_no, page):
    """Single anonymized annual-salary row whose identifier disappeared in OCR."""
    if not (re.search(r'(?i)zanonimizowane\s+dane\s+osobowe',page)
            and re.search(r'(?is)wynagrodzenie\s+brutto.{0,60}(?:r[o0]k|tok)\s+2025',page)):
        return []
    m=re.search(r'(?is)wynagrodzenie\s+brutto.{0,80}?(?:r[o0]k|tok)\s+2025.{0,80}?(\d{1,3}(?:[ .]\d{3})+(?:[,.]\d{2})\s*zł)',page)
    if not m: return []
    val=parse_money(m.group(1))
    if not val or val<1000:return []
    return [SalaryRow(case_pk,institution_pk,placowka,'Lekarz 1','','',None,val,page_no,
                      'single-anonymized-annual-amount','wysoka',norm_space(m.group(0)))]

def parse_annual_named_colon_amount_list(case_pk, institution_pk, placowka, page_no, page):
    """
    Roczne zestawienie w treści maila / OCR:
      ZESTAWIENIE WYNAGRODZEŃ ... LEKARZOM W 2025 ROKU
      KOWALSKI JAN: 58 523,85
      NOWAK ANNA: 46 322,42

    Reguła generyczna: wymaga wyraźnego kontekstu wynagrodzeń lekarzy i roku 2025,
    a następnie co najmniej 3 wierszy 'nazwa: kwota'.
    """
    if not re.search(r'(?is)(?:zestawienie|wykaz|lista).{0,120}wynagrodze[nń].{0,120}(?:lekarz|2025)|wynagrodze[nń].{0,120}lekarz.{0,120}2025', page):
        return []
    out=[]
    for line in page.splitlines():
        raw=norm_space(line)
        m=re.match(
            r'^([A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż .\-]{2,100})\s*:\s*'
            r'(\d{1,3}(?:[ .\u00a0]\d{3})+|\d{4,7})(?:[,.](\d{2}))?\s*(?:zł)?$',
            raw
        )
        if not m:
            continue
        name=norm_space(m.group(1)).strip(' .:-')
        # odrzuć nagłówki i metadane
        if re.search(r'(?i)(zestawienie|wynagrodze[nń]|telefon|nip|regon|krs|ul\.|sp\.j|sp\. z|rok\b)', name):
            continue
        token=m.group(2)
        if m.group(3): token += ','+m.group(3)
        val=parse_money(token)
        if val is None or val<=0:
            continue
        out.append(SalaryRow(case_pk,institution_pk,placowka,name,'','',None,val,page_no,'annual-named-colon-amount','wysoka',raw))
    return out if len(out)>=3 else []

