"""Related vertical, inline and OCR-damaged salary-layout parsers."""
from __future__ import annotations
from typing import Optional
from ..models import SalaryRow
from ..processing.normalization import *
from ..processing.document import _metadata_context

def page_context_contract(lines: list[str], pos: int, fallback: str='') -> str:
    """Parse or process the `page_context_contract` layout/stage."""
    chunk = '\n'.join(lines[max(0, pos - 12):pos + 1])
    return detect_contract(chunk, fallback)

def parse_parallel_name_amount_lists(case_pk: int, institution_pk: Optional[int], placowka: str, doc: str) -> list[SalaryRow]:
    """Parse or process the `parse_parallel_name_amount_lists` layout/stage."""
    text = norm_space(doc)
    m = re.search('(?is)imienna\\s+lista\\s+lekarzy.*?2025\\s*:?\\s*(.*?)łączne\\s+wynagrodzenie\\s+wypłacone\\s+w\\s*2025\\s*roku\\s*:?', text)
    if not m:
        return []
    names_blob = m.group(1).strip(' ,.;')
    after = text[m.end():]
    names = [norm_space(x) for x in names_blob.split(',') if norm_space(x)]
    amounts = []
    for mm in re.finditer('(?<!\\d)(\\d{1,3}(?:[ .]\\d{3})+(?:,\\d{1,2})|\\d{1,6},\\d{1,2})\\s*zł', after, re.I):
        val = parse_money(mm.group(1))
        if val is not None:
            amounts.append(val)
    if not names or len(names) != len(amounts):
        return []
    return [SalaryRow(case_pk, institution_pk, placowka, name, '', '', None, val, None, 'parallel-name-amount-lists', 'wysoka', f'{i}. {name} | {val:.2f}') for i, (name, val) in enumerate(zip(names, amounts), 1)]

def parse_indexed_three_col_continuation(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='') -> list[SalaryRow]:
    """Parse or process the `parse_indexed_three_col_continuation` layout/stage."""
    candidates = []
    for raw in page.splitlines():
        if not raw.strip().startswith('|') or re.fullmatch('\\s*\\|?\\s*:?-{3,}:?\\s*(?:\\|\\s*:?-{3,}:?\\s*)+\\|?\\s*', raw):
            continue
        cells = split_markdown_row(raw)
        if len(cells) != 3:
            continue
        idx_txt = norm_space(cells[0]).strip('* ')
        mid = norm_space(cells[1]).strip('* ')
        valtxt = norm_space(cells[2]).strip('* ')
        if not re.fullmatch('\\d{1,4}[.)]?', idx_txt):
            continue
        if not mid or re.search('(?i)lp\\.?|razem|suma|ogółem|wynagrodzen', mid):
            continue
        vals = money_values(valtxt)
        if len(vals) != 1 or vals[0] <= 0:
            continue
        candidates.append((int(re.sub('\\D', '', idx_txt)), mid, vals[0], norm_space(raw)))
    if len(candidates) < 3:
        return []
    rows = []
    for idx, mid, val, raw in candidates:
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', mid, inherited_contract, None, val, page_no, 'markdown-3col-continuation', 'wysoka', raw))
    return rows

def parse_vertical_label_amount_pairs(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='') -> list[SalaryRow]:
    """Parse or process the `parse_vertical_label_amount_pairs` layout/stage."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    pairs = []
    for i in range(len(lines) - 1):
        label = lines[i]
        amount_line = lines[i + 1]
        if len(label) > 80 or re.fullmatch('[\\d\\s.,/-]+', label):
            continue
        if re.match('^\\d{1,4}[.)]?\\s+', label):
            continue
        if re.search('(?i)razem|suma|wynagrodzen|strona|dyrektor|telefon|nip|regon|krs|brutto|netto|stawka', label):
            continue
        if re.search('(?i)zł\\s*/|zł/mies|zł/godz', label):
            continue
        vals = money_values(amount_line)
        if len(vals) != 1:
            continue
        if not re.fullmatch('\\s*(?:\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})?\\s*(?:zł)?\\s*', amount_line, re.I):
            continue
        if vals[0] <= 0:
            continue
        pairs.append((label, vals[0], f'{label} | {amount_line}'))
    if len(pairs) < 5:
        return []
    return [SalaryRow(case_pk, institution_pk, placowka, label, '', inherited_contract, None, val, page_no, 'vertical-label-amount', 'wysoka', raw) for label, val, raw in pairs]

def parse_vertical_indexname_amount(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str, inherited_contract: str='') -> list[SalaryRow]:
    """Parse or process the `parse_vertical_indexname_amount` layout/stage."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    rows = []
    for i in range(len(lines) - 1):
        m = re.match('^(\\d{1,4})\\)?\\s+(.+)$', lines[i])
        if not m:
            continue
        name = norm_space(m.group(2))
        if not re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', name):
            continue
        nxt = lines[i + 1]
        nxt_money = re.sub('\\s+,', ',', nxt)
        vals = money_values(nxt_money)
        if len(vals) != 1:
            continue
        if not re.fullmatch('\\s*\\d[\\d ]*(?:\\s*,\\s*\\d{1,2})?\\s*(?:zł)?\\s*', nxt, re.I):
            continue
        val = vals[0]
        if val <= 0:
            continue
        rows.append(SalaryRow(case_pk, institution_pk, placowka, name, '', inherited_contract, None, val, page_no, 'vertical-index-name-amount', 'wysoka', f'{m.group(1)} {name} | {nxt}'))
    if len(rows) < 5:
        return []
    return rows

def parse_ocr_contract_amount_list(case_pk: int, institution_pk: Optional[int], placowka: str, page_no: int, page: str) -> list[SalaryRow]:
    """Parse or process the `parse_ocr_contract_amount_list` layout/stage."""
    rows = []
    seen_raw = set()
    for line in page.splitlines():
        raw = norm_space(line)
        if not raw or raw in seen_raw:
            continue
        seen_raw.add(raw)
        is_business = bool(re.search('(?i)gospodarcza', raw))
        is_civil = bool(re.search('(?i)(?:cywilno|qwilno|cwilno|ewiino|wiino).?prawna|umowa.{0,20}prawna', raw))
        if not (is_business or is_civil):
            continue
        amount_source = re.sub('(?<=\\d)-(?=\\d{3}[,.]\\d{2}\\b)', ' ', raw)
        toks = re.findall('(?<!\\d)(\\d{1,7}(?:[ .]\\d{3})*(?:,\\d{2})|\\d{1,3}(?:\\.\\d{3})+(?:,\\d{2}))(?!\\d)', amount_source)
        if not toks:
            continue
        tok = toks[-1]
        val = parse_money(tok)
        if val is None or val <= 0:
            continue
        contract = 'działalność gospodarcza' if is_business else 'umowa cywilnoprawna'
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {len(rows) + 1}', '', contract, None, val, page_no, 'ocr-contract-amount-list', 'średnia', raw))
    if len(rows) < 10:
        return []
    out = []
    prev = None
    for r in rows:
        key = (r.typ_umowy, round(r.brutto or 0, 2))
        if key == prev:
            continue
        out.append(r)
        prev = key
    for i, r in enumerate(out, 1):
        r.nazwa = f'Lekarz {i}'
    return out

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

def parse_vertical_index_code_label_amount(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_vertical_index_code_label_amount` layout/stage."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i < len(lines) - 2:
        m = re.match('^(\\d{1,4})\\s+([A-Za-z0-9/.-]{3,20})$', lines[i])
        if m and i + 2 < len(lines):
            label = lines[i + 1]
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and re.search('(?i)lekarz|kontrakt|umow|kartotek|wynagrod|asystent|kierownik|stażysta|stazysta|rezydent', label):
                ct = detect_contract(label)
                out.append(SalaryRow(case_pk, institution_pk, placowka, m.group(2), label, ct, None, vals[0], page_no, 'vertical-index-code-label-amount', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        if re.fullmatch('\\d{1,4}', lines[i]) and i + 2 < len(lines):
            label = lines[i + 1]
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and re.search('(?i)lekarz|kontrakt|umow|kartotek|wynagrod|asystent|kierownik|stażysta|stazysta|rezydent', label):
                ct = detect_contract(label)
                out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {lines[i]}', label, ct, None, vals[0], page_no, 'vertical-index-code-label-amount', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 3 else []

def parse_parallel_index_amount_columns(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_parallel_index_amount_columns` layout/stage."""
    out = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith('|'):
            continue
        cc = split_md_row(raw)
        if len(cc) != 4 or is_separator_row(cc):
            continue
        i1 = re.fullmatch('\\d{1,4}', norm_space(cc[0]))
        i2 = re.fullmatch('\\d{1,4}', norm_space(cc[2])) if norm_space(cc[2]) else None
        c1 = norm_space(cc[1])
        c3 = norm_space(cc[3])
        money_only = re.compile('^\\s*(?:\\d{1,3}(?:[ .]\\d{3})+|\\d{4,7})(?:,\\d{1,2})?\\s*(?:zł)?\\s*$', re.I)
        a = money_values(c1) if money_only.fullmatch(c1) else []
        b = money_values(c3) if money_only.fullmatch(c3) else []
        if i1 and len(a) == 1 and (a[0] >= 1000):
            out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {i1.group()}', '', '', None, a[0], page_no, 'parallel-index-amount', 'wysoka', norm_space(raw)))
        if i2 and len(b) == 1 and (b[0] >= 1000):
            out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {i2.group()}', '', '', None, b[0], page_no, 'parallel-index-amount', 'wysoka', norm_space(raw)))
    idx = []
    for r in out:
        m = re.search('(\\d+)$', r.nazwa)
        idx.append(int(m.group(1)) if m else -1)
    return out if len(out) >= 10 and len(set(idx)) == len(idx) else []

def parse_vertical_idx_code_gross_net(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_vertical_idx_code_gross_net` layout/stage."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i < len(lines) - 2:
        m = re.match('^(\\d{1,4})\\s+([A-Za-z0-9/.-]{2,30})$', lines[i])
        if m:
            a = money_values(lines[i + 1])
            b = money_values(lines[i + 2])
            if len(a) == 1 and len(b) == 1 and (a[0] > 0):
                out.append(SalaryRow(case_pk, institution_pk, placowka, m.group(2), '', '', b[0], a[0], page_no, 'vertical-idx-code-gross-net', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 3 else []

def parse_lekarz_inline_anon_list(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_lekarz_inline_anon_list` layout/stage."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    rows = []
    numbered = []
    first_unnum = None
    for raw in lines:
        m = re.fullmatch('(?i)Lekarz\\s+(\\d{1,4})\\s*(?:\\||[-–—])?\\s*(\\d[\\d .]*,\\d{2})', raw)
        if m:
            val = parse_money(m.group(2))
            if val and val > 0:
                numbered.append((int(m.group(1)), val, raw))
            continue
        m0 = re.fullmatch('(?i)Lekarz\\s*\\|\\s*(\\d[\\d .]*,\\d{2})', raw)
        if m0:
            val = parse_money(m0.group(1))
            if val and val > 0:
                first_unnum = (val, raw)
    if len(numbered) < 5:
        return []
    ids = {x[0] for x in numbered}
    if first_unnum and 2 in ids and (1 not in ids):
        rows.append(SalaryRow(case_pk, institution_pk, placowka, 'Lekarz 1', '', '', None, first_unnum[0], page_no, 'anon-lekarz-inline-list', 'wysoka', first_unnum[1]))
    for idx, val, raw in numbered:
        rows.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', '', '', None, val, page_no, 'anon-lekarz-inline-list', 'wysoka', raw))
    return rows

def parse_indexed_single_salary_markdown(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_indexed_single_salary_markdown` layout/stage."""
    out = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith('|'):
            continue
        cc = split_md_row(raw)
        if len(cc) < 3 or is_separator_row(cc):
            continue
        idx = norm_space(cc[0]).rstrip('.')
        if not re.fullmatch('\\d{1,4}', idx):
            continue
        vals = []
        for j, c in enumerate(cc[1:], 1):
            toks = re.findall('(?<!\\d)(\\d{1,3}(?:[ .]\\d{3})+(?:,\\d{2})?|\\d{4,7},\\d{2})(?!\\d)', norm_space(c))
            for tok in toks:
                v = parse_money(tok)
                if v is not None:
                    vals.append((j, v))
        if len(vals) != 1 or vals[0][1] <= 0:
            continue
        j, val = vals[0]
        name = norm_space(cc[1]) or f'Lekarz {idx}'
        spec = norm_space(cc[2]) if len(cc) > 3 and j != 2 else ''
        if re.search('(?i)razem|suma|ogółem', name):
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, name, spec, '', None, val, page_no, 'indexed-single-salary-md', 'wysoka', norm_space(raw)))
    return out if len(out) >= 1 else []

def parse_indexed_total_gross_continuation(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_indexed_total_gross_continuation` layout/stage."""
    out = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith('|'):
            continue
        cc = split_md_row(raw)
        if len(cc) < 6 or is_separator_row(cc):
            continue
        idx = norm_space(cc[0]).rstrip('.')
        codecell = norm_space(cc[1])
        if not re.fullmatch('\\d{1,4}', idx):
            continue
        if not re.fullmatch('[A-Za-z]-?\\d{2,5}|[A-Za-z0-9/_-]{3,20}', codecell):
            continue
        lastvals = money_values(cc[-1])
        if len(lastvals) != 1 or lastvals[0] <= 0:
            continue
        spec = norm_space(cc[2])
        out.append(SalaryRow(case_pk, institution_pk, placowka, codecell, spec, '', None, lastvals[0], page_no, 'indexed-total-gross-continuation', 'wysoka', norm_space(raw)))
    return out

def parse_salary_bracket_index_table(case_pk, institution_pk, placowka, page_no, page, full_doc):
    """
    Tabela z rozłącznymi koszykami wynagrodzeń, np.:
      <500k | >500k | >1m

    Każdy Lp. oznacza jednego lekarza. Jeśli OCR przesunie kwotę następnego
    lekarza do poprzedniego wiersza, np.:
      129 | ... | 471 233 | 875 605 |
      130 | ... |         |         |
    rozdzielamy:
      129 -> 471 233
      130 -> 875 605

    Reguła działa wyłącznie dla tabel z rozłącznymi progami wynagrodzeń,
    więc nie dotyczy tabel brutto/netto ani UoP/zlecenie/kontrakt.
    """
    if not (
        re.search(r"(?i)<\s*500[ .]?000", full_doc)
        and re.search(r"(?i)>\s*500[ .]?000", full_doc)
        and re.search(r"(?i)>\s*1[ .]?000[ .]?000", full_doc)
    ):
        return []

    parsed = []
    for raw in page.splitlines():
        if not raw.lstrip().startswith("|"):
            continue
        cc = split_md_row(raw)
        if len(cc) < 3 or is_separator_row(cc):
            continue

        idx = norm_space(cc[0]).rstrip(".")
        if not re.fullmatch(r"\d{1,4}", idx):
            continue

        spec = norm_space(cc[1])
        if not spec:
            continue

        vals = []
        for c in cc[2:]:
            vals.extend([v for v in money_values(c) if v > 0])

        parsed.append((int(idx), spec, vals, norm_space(raw)))

    if len(parsed) < 2:
        return []

    by_idx = {x[0]: x for x in parsed}
    out = []
    consumed = set()

    for idx, spec, vals, raw in parsed:
        if idx in consumed:
            continue

        # Normalny przypadek: jeden lekarz, jedna kwota w jednym koszyku.
        if len(vals) == 1:
            out.append(SalaryRow(
                case_pk, institution_pk, placowka,
                f"Lekarz {idx}", spec, "kontrakt/cywilnoprawna",
                None, vals[0], page_no,
                "salary-bracket-index", "wysoka", raw
            ))
            continue

        # OCR shift: dwa wynagrodzenia w wierszu N, następny wiersz N+1 pusty.
        if len(vals) == 2:
            nxt = by_idx.get(idx + 1)
            if nxt and len(nxt[2]) == 0:
                out.append(SalaryRow(
                    case_pk, institution_pk, placowka,
                    f"Lekarz {idx}", spec, "kontrakt/cywilnoprawna",
                    None, vals[0], page_no,
                    "salary-bracket-index", "wysoka", raw
                ))
                out.append(SalaryRow(
                    case_pk, institution_pk, placowka,
                    f"Lekarz {idx + 1}", nxt[1], "kontrakt/cywilnoprawna",
                    None, vals[1], page_no,
                    "salary-bracket-index", "wysoka",
                    raw + " | shifted_to_next_lp"
                ))
                consumed.add(idx + 1)

    return out

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

def parse_vertical_role_named_amount(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_vertical_role_named_amount` layout/stage."""
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    role = ''
    i = 0
    stop_re = re.compile('(?i)^umowa\\b|^kontrakt\\b|^l\\.?p\\.?$|^wypłacone\\b|^nazwisko\\b')
    while i < len(lines):
        low = lines[i].lower()
        if low in {'ordynator', 'koordynator'}:
            role = low
            i += 1
            continue
        if role and stop_re.search(lines[i]):
            role = ''
            i += 1
            continue
        if role and re.fullmatch('\\d{1,3}', lines[i]):
            idx = lines[i]
            names = []
            j = i + 1
            found = False
            while j < len(lines) and len(names) < 3:
                if stop_re.search(lines[j]) or lines[j].lower() in {'ordynator', 'koordynator'}:
                    break
                vals = money_values(lines[j])
                if len(vals) == 1 and re.fullmatch('\\d[\\d ]*(?:,\\d{1,2})?', lines[j]):
                    name = norm_space(' '.join(names))
                    if name:
                        out.append(SalaryRow(case_pk, institution_pk, placowka, name, role, '', None, vals[0], page_no, 'vertical-role-named-amount', 'wysoka', f'{role} | {idx} | {name} | {lines[j]}'))
                    i = j + 1
                    found = True
                    break
                if re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', lines[j]):
                    names.append(lines[j])
                j += 1
            if found:
                continue
        i += 1
    return out

def parse_numbered_amount_only_series(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_numbered_amount_only_series` layout/stage."""
    m = re.search('(?is)wynagrodzenia.{0,160}(?:kształtowały|ksztaltowaly|następująco|nastepujaco)\\s*:\\s*(.+)', page)
    if not m:
        return []
    tail = m.group(1)
    pat = re.compile('(?<!\\d)(\\d{1,3})[.)]\\s*(\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})\\s*zł', re.I)
    out = []
    for mm in pat.finditer(tail):
        am = re.search('(\\d{1,3}(?:[ .]\\d{3})+|\\d{1,7})(?:,\\d{1,2})', mm.group(0))
        if not am:
            continue
        val = parse_money(am.group(0))
        if val is None or val <= 0:
            continue
        out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {mm.group(1)}', '', '', None, val, page_no, 'numbered-amount-only-series', 'wysoka', norm_space(mm.group(0))))
    return out if len(out) >= 5 else []

def parse_vertical_named_salary_table(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_vertical_named_salary_table` layout/stage."""
    if not (re.search('(?i)imię i nazwisko|imie i nazwisko', page) and re.search('(?i)kwota wynagrodzenia.*2025', page)):
        return []
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i + 2 < len(lines):
        if re.fullmatch('\\d{1,4}', lines[i]):
            name = lines[i + 1]
            vals = money_values(lines[i + 2])
            if re.search('[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]', name) and len(vals) == 1 and (vals[0] > 0):
                out.append(SalaryRow(case_pk, institution_pk, placowka, name, '', '', None, vals[0], page_no, 'vertical-named-salary-table', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 3 else []

def parse_two_section_vertical_salary(case_pk, institution_pk, placowka, page_no, page):
    """Parse or process the `parse_two_section_vertical_salary` layout/stage."""
    if not (re.search('(?i)wynagrodzenie lekarzy zatrudnionych', page) and re.search('(?i)umow[ęe] o prac[ęe]', page) and re.search('(?i)umow[ęe] cywilnoprawn', page)):
        return []
    lines = [norm_space(x) for x in page.splitlines() if norm_space(x)]
    out = []
    i = 0
    while i + 2 < len(lines):
        m = re.fullmatch('(?i)Lekarz\\s+(\\d{1,4})', lines[i])
        if m:
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and vals[0] > 0:
                out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {m.group(1)}', lines[i + 1], 'umowa o pracę', None, vals[0], page_no, 'two-section-vertical', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        idx = lines[i].rstrip('.')
        if re.fullmatch('\\d{1,4}', idx) and re.search('(?i)dyżur|dyzur|praca dzienna', lines[i + 1]):
            vals = money_values(lines[i + 2])
            if len(vals) == 1 and vals[0] > 0:
                out.append(SalaryRow(case_pk, institution_pk, placowka, f'Lekarz {idx}', lines[i + 1], 'umowa cywilnoprawna', None, vals[0], page_no, 'two-section-vertical', 'wysoka', ' | '.join(lines[i:i + 3])))
                i += 3
                continue
        i += 1
    return out if len(out) >= 5 else []

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

def parse_ocr_broken_numbered_salary_table(case_pk, institution_pk, placowka, page_no, page):
    """Reconstruct a broken OCR table only when later doctor numbers anchor the sequence."""
    if not re.search(r'(?i)oznaczenie\s+lekarza', page):
        return []
    if not re.search(r'(?is)roczne\s+wynagrodzenie.{0,120}(?:zł|nfz|2025)', page):
        return []

    explicit=[]
    # Flexible OCR: Lekarz nr 10 | 116 370; Lekarznr12 _ | 235 955
    exp_re=re.compile(
        r'(?i)lekarz\s*nr\s*(\d{1,3})\b.{0,18}?'
        r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})?',
        re.S
    )
    for m in exp_re.finditer(page):
        val=parse_money(m.group(2))
        if val is not None and val>=1000:
            explicit.append((int(m.group(1)), val, m.start(), norm_space(m.group(0))))
    if len(explicit)<3:
        return []
    explicit.sort()
    ids=[x[0] for x in explicit]
    if ids != list(range(ids[0], ids[0]+len(ids))):
        return []
    anchor_idx=ids[0]
    if anchor_idx<=2:
        return []
    anchor_pos=min(x[2] for x in explicit)

    # Only money-only lines between the salary header and the first explicit doctor label.
    hm=re.search(r'(?is)roczne\s+wynagrodzenie.{0,160}(?:zł|nfz)', page)
    start=hm.end() if hm else re.search(r'(?i)oznaczenie\s+lekarza',page).end()
    prefix=page[start:anchor_pos]
    prior=[]
    for raw in prefix.splitlines():
        line=norm_space(raw).strip('|_ ')
        if not line:
            continue
        # tolerate trailing OCR junk such as 's' or '|', but not ordinary prose.
        m=re.fullmatch(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})?\s*[A-Za-z|_]?', line)
        if not m:
            continue
        tok=re.match(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{1,2})?',line).group(0)
        val=parse_money(tok)
        if val is not None and val>=1000 and val != 2025:
            prior.append((val,norm_space(raw)))

    expected=anchor_idx-1
    # Exact sequence, or exactly one OCR-lost salary before the anchor.
    if len(prior) not in (expected, expected-1):
        return []
    missing=[] if len(prior)==expected else [len(prior)+1]
    comment='Rekonstrukcja z uszkodzonego OCR.'
    if missing:
        comment += f" Brak odczytywalnej kwoty dla Lekarz {missing[0]}; nie utworzono tego rekordu."

    out=[]
    for idx,(val,raw) in enumerate(prior,1):
        out.append(SalaryRow(case_pk,institution_pk,placowka,f'Lekarz {idx}','','',
                             None,val,page_no,'ocr-broken-numbered-table','średnia',raw,comment))
    for idx,val,_,raw in explicit:
        out.append(SalaryRow(case_pk,institution_pk,placowka,f'Lekarz {idx}','','',
                             None,val,page_no,'ocr-broken-numbered-table','średnia',raw,comment))
    return out

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

def parse_parallel_doctor_amount_lists(case_pk, institution_pk, placowka, page_no, page):
    """
    Dwie równoległe listy lekarzy i wynagrodzeń.
    Zachowujemy pozycję każdego tokenu, a nieczytelną kwotę pomijamy bez
    przesuwania kolejnych par.

    Dopuszczamy jeden bezpieczny repair OCR nazwisk:
    jeśli lista jest niemal wyłącznie listą pojedynczych nazwisk, liczba
    kwot jest większa dokładnie o 1, a dokładnie jeden element ma postać
    "Nazwisko Nazwisko", rozdzielamy ten element na dwie osoby.
    """
    m1=re.search(
        r'(?is)\bLekarze\s*:\s*(.+?)\bWynagrodzenia\s+lekarzy\s*:\s*(.+)',
        page
    )
    if not m1:
        return []

    names_part=m1.group(1)
    amounts_part=m1.group(2)

    raw_names=[norm_space(x).strip(" .") for x in re.split(r'[,;\n]+',names_part) if norm_space(x)]
    names=[]
    for x in raw_names:
        if re.search(r'(?i)z poważaniem|dyrektor|telefon|email|www\.|załącznik',x):
            break
        if re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]',x):
            names.append(x)

    # Odetnij stopkę po liście kwot.
    amounts_part=re.split(
        r'(?i)\n\s*(?:Pozdrawiam|Z poważaniem|Dyrektor|Prezes|Główny Specjalista)\b',
        amounts_part,maxsplit=1
    )[0]

    # Normalizacja "97.125, 00" oraz sklejenia "11.970,00425.910,00".
    s=re.sub(r',\s+(\d{2})(?=[;\s])',r',\1',amounts_part)
    s=re.sub(r'(,\d{2})(?=\d)',r'\1;',s)
    amount_parts=[norm_space(x) for x in re.split(r';|\n',s) if norm_space(x)]

    # Gdy kwot jest o 1 więcej, spróbuj bezpiecznie rozdzielić jedno sklejone nazwisko.
    if len(amount_parts)==len(names)+1:
        single_ratio=sum(1 for x in names if len(x.split())==1)/max(1,len(names))
        candidates=[
            (i,x) for i,x in enumerate(names)
            if len(x.split())==2
            and '-' not in x
            and all(re.fullmatch(r'[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+',w) for w in x.split())
        ]
        if single_ratio>=0.8 and len(candidates)==1:
            i,x=candidates[0]
            a,b=x.split()
            names=names[:i]+[a,b]+names[i+1:]

    if len(names)<3 or len(names)!=len(amount_parts):
        return []

    out=[]
    unreadable=[]
    for idx,(name,part) in enumerate(zip(names,amount_parts),1):
        # Kwota musi być pełnym tokenem; nie naprawiamy arbitralnie np. 43.37,73.
        mm=re.fullmatch(
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7}),(\d{2})\s*(?:zł)?[.,]?',
            part,re.I
        )
        if not mm:
            unreadable.append((idx,name,part))
            continue
        val=parse_money(mm.group(1)+','+mm.group(2))
        if val is None or val<=0:
            unreadable.append((idx,name,part))
            continue
        row=SalaryRow(
            case_pk,institution_pk,placowka,name,"","",
            None,val,page_no,"parallel-doctor-amount-lists","wysoka",
            f"{idx} | {name} | {part}"
        )
        out.append(row)

    # Wymagamy, aby prawie cała lista była czytelna.
    if len(out)<3 or len(out) < len(names)-2:
        return []
    if unreadable:
        note="; ".join(f"poz. {i}: {n} / {raw}" for i,n,raw in unreadable)
        for r in out:
            r.komentarz=(r.komentarz+"; " if r.komentarz else "") + \
                "Lista równoległa; pominięto nieczytelną pozycję OCR: " + note
    return out

def parse_anonymous_amount_only_series(case_pk, institution_pk, placowka, page_no, page):
    """
    Anonimowa seria samych kwot po jednoznacznym nagłówku:
      Kwoty brutto:
      182.685,60
      249.794,96
      ...

    Wymagany jest kontekst lekarzy/wynagrodzeń 2025 oraz minimum 3 kwoty.
    """
    if not re.search(r'(?i)\b(?:kwoty\s+brutto|kwoty\s+netto)\s*:', page):
        return []
    if not (re.search(r'(?i)lekarz',page) or re.search(r'(?i)wynagrodze[nń]',page)):
        return []

    # Bierz tylko fragment po nagłówku.
    m=re.search(r'(?is)\b(?:kwoty\s+brutto|kwoty\s+netto)\s*:\s*(.+)',page)
    if not m:
        return []
    tail=m.group(1)

    vals=[]
    raws=[]
    for line in tail.splitlines():
        raw=norm_space(line)
        if not raw:
            continue
        # przerwij na podpisie/stopce lub nowej sekcji tekstowej
        if re.search(r'(?i)^z poważaniem|^dyrektor\b|^prezes\b|^--$|^załącznik',raw):
            break
        mm=re.fullmatch(
            r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{2})\s*(?:zł)?[.,]?',
            raw,re.I
        )
        if not mm:
            # toleruj numerację "1. 182.685,60"
            mm=re.fullmatch(
                r'\d{1,3}[.)]\s*(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{2})\s*(?:zł)?[.,]?',
                raw,re.I
            )
        if not mm:
            continue
        am=re.search(r'(\d{1,3}(?:[ .]\d{3})+|\d{4,7})(?:,\d{2})',raw)
        if not am:
            continue
        val=parse_money(am.group(0))
        if val is not None and val>0:
            vals.append(val); raws.append(raw)

    if len(vals)<3:
        return []

    # Netto/brutto z nagłówka
    is_netto=bool(re.search(r'(?i)kwoty\s+netto',page))
    out=[]
    for idx,(val,raw) in enumerate(zip(vals,raws),1):
        out.append(SalaryRow(
            case_pk,institution_pk,placowka,f"Lekarz {idx}","","",
            val if is_netto else None,
            None if is_netto else val,
            page_no,"anonymous-amount-only-series","wysoka",raw
        ))
    return out

def parse_annual_amount_contract_lines(case_pk, institution_pk, placowka, page_no, page):
    """Annual anonymous list: one salary amount and contract type on each line."""
    if not (re.search(r'(?i)wynagrodzenia\s+lekarzy\s+za\s+rok\s+2025', page)
            and re.search(r'(?i)bez\s+imion\s+i\s+nazwisk|bez\s+.*nazwisk', page)):
        return []
    candidates=[]
    for raw in page.splitlines():
        vals=money_values(raw)
        ct=detect_contract(raw, '')
        if len(vals)==1 and ct and re.search(r'(?i)umow|kontrakt|cywilnopraw',raw) and not _metadata_context(raw):
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

def parse_forma_name_amount_ocr(case_pk, institution_pk, placowka, page_no, page):
    """OCR table headed FORMA where each row starts with a person/practice and its annual amount."""
    if not (re.search(r'(?m)^FORMA\s*$',page) or re.search(r'(?m)^FORMA\s+[A-ZĄĆĘŁŃÓŚŹŻ]',page)):
        return []
    start=re.search(r'(?m)^FORMA\b',page)
    block=page[start.start():] if start else page
    out=[]
    for raw in block.splitlines():
        line=norm_space(raw)
        if line=='FORMA': continue
        cells=money_cells(line)
        if not cells: continue
        prev=0
        for tok,val in cells:
            pos=line.find(tok,prev)
            label=norm_space(line[prev:pos].strip(' -–—|'))
            label=re.sub(r'(?i)^FORMA\s+','',label).strip()
            prev=pos+len(tok)
            # A later bare OCR number has no alphabetic label and is ignored.
            if not label or not re.search(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]',label): continue
            if _metadata_context(label) or val<=0 or val>5_000_000: continue
            if re.search(r'(?i)kierownik\s+dzia[łl]u|koniec\s+strony',label): continue
            out.append(SalaryRow(case_pk,institution_pk,placowka,label,'','',None,val,page_no,
                                 'forma-name-amount-ocr','średnia',line))
    return out if len(out)>=5 else []

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

