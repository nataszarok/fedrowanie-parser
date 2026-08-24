"""Document segmentation, correspondence classification and row-quality filters."""
from __future__ import annotations

from ..constants import *
from typing import Optional
from ..models import SalaryRow
from .normalization import *

# Document/correspondence constants retained from v35.


__all__ = [
    "split_pages",
    "page_is_2025_relevant",
    "suspicious_amount",
    "deduplicate",
    "classify_nonannual_response",
    "extract_recipient_messages",
    "correspondence_status",
    "is_metadata_context",
    "topn_comment",
    "filter_registry_capital_false_rows",
    "aggregate_count_total_guard",
    "is_correction_message",
    "prefer_latest_correction",
    "is_wrong_month",
    "recipient_document",
    "page_is_group_aggregate_salary_table",
]


def split_pages(text: str) -> list[tuple[int, str]]:
    """Split a document into parser page blocks while preserving page order."""
    src = text or ''
    matches = list(PAGE_RE.finditer(src))
    if not matches:
        return [(1, src)]
    out = [(int(m.group(1)), m.group(2)) for m in matches]
    spans = []
    last = 0
    marker_blocks = list(re.finditer('-+\\s*początek strony\\s+\\d+\\s*-+.*?-+\\s*koniec strony\\s+\\d+\\s*-+', src, re.I | re.S))
    for b in marker_blocks:
        if b.start() > last:
            spans.append(src[last:b.start()])
        last = b.end()
    if last < len(src):
        spans.append(src[last:])
    pseudo = 10000
    for chunk in spans:
        money_n = len(money_cells(chunk))
        salary_sem = bool(re.search('(?i)wynagrod|gospodarcza|cywilno.?prawna|kontrakt|umowa o pracę|specjalista|lekarz', chunk))
        if money_n >= 5 and salary_sem:
            out.append((pseudo, chunk))
            pseudo += 1
    return out

def page_is_2025_relevant(page: str, doc: str) -> bool:
    """Return whether a page is relevant to remuneration data for 2025."""
    years = {int(x) for x in YEAR_OTHER_RE.findall(page)}
    if years and YEAR not in years:
        tableish = page.count('|') >= 8 or len(money_cells(page)) >= 8
        correspondence = re.search('(?i)wniosek|odpowiedzi na wniosek|data odebrania|temat:|koszalin, dnia|szczecin, dnia', page)
        doc_years = {int(x) for x in YEAR_OTHER_RE.findall(doc)}
        salary_rich = len(money_cells(page)) >= 10 and bool(re.search('(?i)wynagrod|gospodarcza|cywilno.?prawna|qwilno.?prawna|kontrakt|umowa o pracę|lekarz|specjalista', page))
        explicit_wrong_period = bool(re.search('(?i)(?:stycze[nń]|luty|marzec|kwiecie[nń]|maj|czerwiec|lipiec|sierpie[nń]|wrzesie[nń]|październik|pazdziernik|listopad|grudzie[nń]).{0,30}\\b(?:2024|2026|2027)\\b', page))
        if not (tableish and YEAR in doc_years and (not correspondence) or (salary_rich and YEAR in doc_years and (not explicit_wrong_period))):
            return False
    return True

def suspicious_amount(row: SalaryRow) -> bool:
    """Parse or process the `suspicious_amount` layout/stage."""
    val = row.brutto if row.brutto is not None else row.netto
    if val is None or val <= 0:
        return True
    if 1900 <= val <= 2100 and re.search('\\b20\\d{2}\\b', row.raw_row):
        return True
    if val > 20000000:
        return True
    return False

def deduplicate(rows: Iterable[SalaryRow]) -> list[SalaryRow]:
    """Remove duplicate salary rows while preserving the strongest source record."""
    rows = list(rows)
    markdown_amounts = {(r.case_pk, round(r.brutto if r.brutto is not None else r.netto, 2)) for r in rows if r.parser.startswith('markdown') and (r.brutto is not None or r.netto is not None)}
    seen = set()
    seen_numbered = set()
    out = []
    for r in rows:
        val = r.brutto if r.brutto is not None else r.netto
        if val is None or val <= 0:
            continue
        raw = norm_space(r.raw_row).lower()
        if r.parser == 'plain-split' and ('| --- |' in raw or '|---|' in raw) and ((r.case_pk, round(val, 2)) in markdown_amounts):
            continue
        exact = (r.case_pk, r.strona, norm_space(r.nazwa).lower(), norm_space(r.specjalizacja).lower(), norm_space(r.typ_umowy).lower(), r.netto, r.brutto, raw)
        if exact in seen:
            continue
        seen.add(exact)
        m = re.match('^\\|?\\s*\\*{0,2}(\\d{1,4})\\*{0,2}[.)]?\\s*\\|', raw)
        if m:
            numbered = (r.case_pk, int(m.group(1)), round(val, 2), norm_space(r.typ_umowy).lower())
            if numbered in seen_numbered:
                continue
            seen_numbered.add(numbered)
        out.append(r)
    return out

def classify_nonannual_response(doc: str) -> tuple[bool, str]:
    """Classify responses that do not provide annual salary data."""
    date_count = len(re.findall('\\b2025-\\d{2}-\\d{2}\\b', doc))
    invoice_code_count = len(re.findall('\\b[A-ZŻŹĆĄŚĘŁÓŃ]{1,8}/2025/\\d{1,2}/\\d+\\b', doc))
    invoice_word_count = len(re.findall('(?i)\\bfaktur\\w*\\b|\\bnr\\s+faktur', doc))
    if date_count >= 8 and (invoice_code_count >= 5 or invoice_word_count >= 2):
        return (True, 'accounting_invoice_register')
    tariff_core = re.search('(?i)współczynnik\\s+pracy|wspolczynnik\\s+pracy', doc) and re.search('(?i)wynagrodzenie\\s+zasadnicze', doc)
    rate_core = re.search('(?i)stawki\\s+lekarzy|rozliczenie\\s+następuje\\s+za\\s+godzin|rozliczenie\\s+nastepuje\\s+za\\s+godzin|punkty\\s+za\\s+wykonane\\s+procedury|procedury.*stawki', doc)
    if tariff_core and rate_core:
        return (True, 'tariffs_coefficients_or_procedure_rates')
    for line in doc.splitlines():
        if not line.strip().startswith('|'):
            continue
        romans = len(re.findall('\\|\\s*(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\\s*(?=\\|)', line, re.I))
        if romans >= 4 and (not re.search('(?i)łącznie|lacznie|suma|2025', line)):
            return (True, 'periodic_month_matrix_without_annual_total')
    header_lines = [line.lower() for line in doc.splitlines() if line.strip().startswith('|')]
    monthly_header = any((('miesiąc' in line or 'miesiac' in line) and sum((k in line for k in ['najwyższe miesięczne', 'najwyzsze miesieczne', 'średnie miesięczne', 'srednie miesieczne', 'najniższe miesięczne', 'najnizsze miesieczne', 'mediana'])) >= 3 for line in header_lines))
    if monthly_header:
        annual_named = 0
        for line in doc.splitlines():
            if re.search(MONTH_NAME_RE, line, re.I):
                continue
            if re.search('\\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż-]+\\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż-]+\\b', line) and re.search('\\d{1,3}(?:[ .]\\d{3})+(?:,\\d{1,2})?\\s*zł', line, re.I):
                annual_named += 1
        if annual_named < 2:
            return (True, 'monthly_group_statistics_not_individual_annual_list')
    if re.search('(?is)\\|\\s*Oddziały\\s*\\|.*?Minimalny\\s+przychód\\s+za\\s+2025.*?Maksymalny\\s+przychód\\s+za\\s+2025', doc) and re.search('(?i)uniemożliwia\\s+porównanie.*poszczególnych\\s+lekarzy|uniemozliwia\\s+porownanie.*poszczegolnych\\s+lekarzy', doc):
        return (True, 'group_min_max_not_individual_salaries')
    wrong_period = re.search(f'(?is)Dane\\s+za\\s*\\|?\\s*{MONTH_NAME_RE}\\s+(20\\d{{2}})\\s*r?\\.?', doc)
    if wrong_period and wrong_period.group(1) != '2025':
        if re.search('(?i)wynagrodzenie\\s+(?:brutto|netto)\\s+za\\s+1\\s+miesiąc|średnia\\s+wszystkich\\s+lekarzy|mediana\\s+wszystkich\\s+lekarzy', doc):
            return (True, 'wrong_period_monthly_statistics')
    return (False, '')

def extract_recipient_messages(doc: str) -> tuple[str, dict]:
    """Keep recipient-side messages and remove requester/quoted-thread noise."""
    pos = doc.find('Znormalizowana odpowiedź')
    thread = doc[pos:] if pos >= 0 else doc
    lines = thread.splitlines()
    headers = []
    for i in range(len(lines) - 2):
        sender_line = lines[i + 1].strip()
        date_line = lines[i + 2].strip()
        if sender_line.startswith('przez ') and THREAD_DATE_RE.match(date_line):
            headers.append((i, lines[i].strip(), sender_line[6:].strip(), date_line))
    if not headers:
        return ('', {'thread_detected': False, 'all_messages': 0, 'recipient_messages': 0, 'substantive_recipient_messages': 0})
    recipient_parts = []
    recipient_messages = 0
    substantive = 0
    for j, (i, subject, sender, date) in enumerate(headers):
        end = headers[j + 1][0] if j + 1 < len(headers) else len(lines)
        body = '\n'.join(lines[i + 3:end]).strip()
        if REQUESTER_SENDER_RE.match(sender):
            continue
        recipient_messages += 1
        if AUTO_REPLY_RE.search(body) or AUTO_REPLY_RE.search(subject):
            continue
        clean = body
        attachment_pos = None
        for marker in ('Załączniki', 'Załącznik', 'początek strony'):
            p = clean.find(marker)
            if p >= 0 and (attachment_pos is None or p < attachment_pos):
                attachment_pos = p
        quote_scan = clean if attachment_pos is None else clean[:attachment_pos]
        cut_at = None
        for pat in QUOTE_CUT_PATTERNS:
            m = pat.search(quote_scan)
            if m and (cut_at is None or m.start() < cut_at):
                cut_at = m.start()
        if cut_at is not None:
            before_quote = clean[:cut_at].rstrip()
            after_quote = clean[cut_at:]
            attach_positions = [p for marker in ('Załączniki', 'Załącznik', 'początek strony') for p in [after_quote.find(marker)] if p >= 0]
            if attach_positions:
                clean = before_quote + '\n' + after_quote[min(attach_positions):]
            else:
                clean = before_quote
        if not clean.strip():
            continue
        substantive += 1
        recipient_parts.append(f'### WIADOMOŚĆ ODBIORCY\nTemat: {subject}\nData: {date}\n{clean}')
    return ('\n\n'.join(recipient_parts), {'thread_detected': True, 'all_messages': len(headers), 'recipient_messages': recipient_messages, 'substantive_recipient_messages': substantive})

def correspondence_status(doc: str, rows: list[SalaryRow]) -> tuple[str, str]:
    """Summarize whether correspondence contains usable recipient-side data."""
    refusal = bool(re.search('(?is)(?:odmaw\\w*|nie\\s+udostępni\\w*|nie\\s+udzieli\\w*|nie\\s+jest\\s+informacją\\s+publiczną|podlega\\s+ograniczeniu).{0,300}(?:wynagrodze[nń]|imion|nazwisk|danych\\s+osobowych|prywatnoś|prywatnos)', doc))
    anonymized = bool(re.search('(?i)(?:anonimiz|zanonimiz|bez\\s+podawania\\s+imion|bez\\s+imion\\s+i\\s+nazwisk|zestawienie\\s+nie\\s+zawiera\\s+imion|kod\\s+anonimowy|lekarz\\s+\\d+)', doc))
    distribution = bool(re.search('(?is)liczba\\s+lekarzy.{0,180}wynagrodzen.{0,140}przedzia', doc))
    date_count = len(re.findall('\\b2025-\\d{2}-\\d{2}\\b', doc))
    invoice_code_count = len(re.findall('\\b[A-ZŻŹĆĄŚĘŁÓŃ]{1,8}/2025/\\d{1,2}/\\d+\\b', doc))
    invoice_word_count = len(re.findall('(?i)\\bfaktur\\w*\\b|\\bnr\\s+faktur', doc))
    invoices = date_count >= 8 and (invoice_code_count >= 5 or invoice_word_count >= 2)
    tariffs = bool(re.search('(?i)współczynnik\\s+pracy|wspolczynnik\\s+pracy', doc) and re.search('(?i)wynagrodzenie\\s+zasadnicze', doc) and re.search('(?i)stawki\\s+lekarzy|rozliczenie\\s+następuje\\s+za\\s+godzin|rozliczenie\\s+nastepuje\\s+za\\s+godzin|punkty\\s+za\\s+wykonane\\s+procedury|procedury.*stawki', doc))
    periodic_matrix = False
    for line in doc.splitlines():
        if not line.strip().startswith('|'):
            continue
        romans = len(re.findall('\\|\\s*(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\\s*(?=\\|)', line, re.I))
        if romans >= 4 and (not re.search('(?i)łącznie|lacznie|suma|2025', line)):
            periodic_matrix = True
            break
    monthly_group_stats = any((('miesiąc' in line.lower() or 'miesiac' in line.lower()) and sum((k in line.lower() for k in ['najwyższe miesięczne', 'najwyzsze miesieczne', 'średnie miesięczne', 'srednie miesieczne', 'najniższe miesięczne', 'najnizsze miesieczne', 'mediana'])) >= 3 for line in doc.splitlines() if line.strip().startswith('|')))
    group_minmax = bool(re.search('(?is)\\|\\s*Oddziały\\s*\\|.*?Minimalny\\s+przychód\\s+za\\s+2025.*?Maksymalny\\s+przychód\\s+za\\s+2025', doc) and re.search('(?i)uniemożliwia\\s+porównanie.*poszczególnych\\s+lekarzy|uniemozliwia\\s+porownanie.*poszczegolnych\\s+lekarzy', doc))
    wrong_period = bool(re.search(f'(?is)Dane\\s+za\\s*\\|?\\s*{MONTH_NAME_RE}\\s+(?:2024|2026|2027)\\s*r?\\.?', doc) and re.search('(?i)wynagrodzenie\\s+(?:brutto|netto)\\s+za\\s+1\\s+miesiąc|średnia\\s+wszystkich\\s+lekarzy|mediana\\s+wszystkich\\s+lekarzy', doc))
    annual_rows = [r for r in rows if (r.brutto is not None or r.netto is not None) and ((r.brutto or 0) > 0 or (r.netto or 0) > 0)]
    if invoices:
        return ('SUBSTANTIVE_NONCOMPARABLE_DATA', 'accounting_invoice_register')
    if tariffs:
        return ('SUBSTANTIVE_NONCOMPARABLE_DATA', 'tariffs_coefficients_or_procedure_rates')
    if periodic_matrix:
        return ('SUBSTANTIVE_NONCOMPARABLE_DATA', 'periodic_month_matrix_without_annual_total')
    if group_minmax:
        return ('SUBSTANTIVE_AGGREGATE_ONLY', 'group_min_max_not_individual_salaries')
    if wrong_period:
        return ('SUBSTANTIVE_NONCOMPARABLE_DATA', 'wrong_period_monthly_statistics')
    if distribution:
        genuine_rows = [r for r in annual_rows if not re.search('(?i)liczba\\s+lekarzy|przedzia[łl]|^\\s*\\d+(?:\\s*\\|\\s*\\d+){1,3}\\s*$', norm_space(r.raw_row)) and (re.search('(?i)kod\\s+anonimowy|lekarz\\s+\\d+|praktyka\\s+lekarska', r.raw_row) or (r.nazwa and (not re.fullmatch('(?i)lekarz\\s*\\d*', norm_space(r.nazwa)))))]
        if not genuine_rows:
            return ('SUBSTANTIVE_DISTRIBUTION_ONLY', 'salary_distribution_bins')
    if monthly_group_stats:
        explicit_annual_named = 0
        for line in doc.splitlines():
            if re.search(MONTH_NAME_RE, line, re.I):
                continue
            if re.search('\\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż-]+\\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż-]+\\b', line) and re.search('\\d{1,3}(?:[ .]\\d{3})+(?:,\\d{1,2})?\\s*zł', line, re.I):
                explicit_annual_named += 1
        if explicit_annual_named < 2:
            return ('SUBSTANTIVE_AGGREGATE_ONLY', 'monthly_group_statistics_not_individual_annual_list')
    if annual_rows:
        if refusal:
            return ('INDIVIDUAL_ANNUAL_2025_AFTER_OR_WITH_REFUSAL', 'anonymized' if anonymized else 'data_after_refusal')
        return ('INDIVIDUAL_ANNUAL_2025', 'individual_or_anonymous_values')
    aggregate = bool(re.search('(?is)(?:sumaryczna|łączna|laczna)\\s+(?:wartość|wartosc)?\\s*wynagrodze[nń].{0,160}2025|(?:średnia|srednia|mediana|minimalny|maksymalny|najwyższe|najwyzsze|najniższe|najnizsze).{0,180}(?:wynagrodzen|przychod)', doc))
    if aggregate:
        return ('SUBSTANTIVE_AGGREGATE_ONLY', 'aggregate_or_statistics')
    if refusal:
        return ('REFUSAL_NO_SUBSTANTIVE_DATA', 'refusal')
    return ('NO_SUBSTANTIVE_DATA_DETECTED', '')

def topn_comment(doc: str) -> str:
    """Return a human-readable note when the reply explicitly contains only top-N salaries."""
    text = norm_space(doc)
    patterns = [
        r'(?i)(?:zestawienie|wykaz|lista|grup[ęa]|przedstawiono|obejmuj\w*|przekaz\w*).{0,140}?\b(\d{1,3})\s+(?:najwy[żz]szych\s+)?(?:kwot\s+)?(?:wynagrodze[nń]|lekarzy).{0,100}?najwy[żz]sz',
        r'(?i)(?:zestawienie|wykaz|lista|grup[ęa]|przedstawiono|obejmuj\w*|przekaz\w*).{0,140}?\b(\d{1,3})\s+najwy[żz]szych\b',
        r'(?i)\b(\d{1,3})\s+lekarzy\s+z\s+najwy[żz]sz',
        r'(?i)\b(\d{1,3})\s+najwy[żz]szych\s+(?:kwot\s+)?wynagrodze[nń]',
    ]
    nums=[]
    for pat in patterns:
        nums += [int(x) for x in re.findall(pat, text)]
    # Polish word form used frequently in replies.
    if re.search(r'(?i)dziesi[eę][cć]\s+najwy[żz]szych\s+wynagrodze[nń]', text):
        nums.append(10)
    # Some replies explicitly provide separate top-N lists by employment form.
    if nums:
        uniq=[]
        for n in nums:
            if n not in uniq: uniq.append(n)
        if len(uniq)==1:
            n=uniq[0]
            occurrences=len(re.findall(rf'(?i)\b{n}\s+lekarzy\s+z\s+najwy[żz]sz', text))
            if occurrences >= 2:
                return f'Tylko TOP {n} w każdej z kilku kategorii/form zatrudnienia; dane nie obejmują wszystkich lekarzy.'
            return f'Tylko TOP {n} najwyższych wynagrodzeń; dane nie obejmują wszystkich lekarzy.'
        return 'Tylko najwyższe wynagrodzenia (TOP N, osobne kategorie); dane nie obejmują wszystkich lekarzy.'
    return ''

def is_metadata_context(text: str) -> bool:
    """Return whether text looks like metadata rather than a salary record."""
    return bool(re.search(r'(?i)kapita[łl]\s+zak[łl]adowy|\bKRS\b|\bREGON\b|\bNIP\b|kapita[łl]\s+sp[oó][łl]ki|s[ąa]d\s+rejonowy|rejestr\w*\s+s[ąa]dow', text or ''))

def filter_registry_capital_false_rows(rows, doc: str):
    """Guard against OCR splitting e.g. '65 559 000 zł' into Lekarz 65 -> 559000."""
    lines=[norm_space(x) for x in (doc or '').splitlines()]
    out=[]
    for r in rows:
        if r.parser != 'plain-index-amount':
            out.append(r); continue
        m=re.fullmatch(r'(?i)Lekarz\s+(\d{1,4})', norm_space(r.nazwa))
        val=r.brutto if r.brutto is not None else r.netto
        if not m or val is None:
            out.append(r); continue
        idx=m.group(1)
        raw=norm_space(r.raw_row)
        # Exact raw line may itself be a split capital value.
        bad=False
        for i,line in enumerate(lines):
            if line != raw: continue
            ctx=' '.join(lines[max(0,i-14):min(len(lines),i+6)])
            if is_metadata_context(ctx): bad=True; break
        if not bad:
            # Also catch one-line OCR: "Kapitał zakładowy: 65 559 000,00 zł".
            pat=rf'(?is)(?:kapita[łl]\s+zak[łl]adowy|\bKRS\b|\bREGON\b|\bNIP\b).{{0,120}}\b{re.escape(idx)}\s+{int(val):,}'.replace(',', r'[ .]?')
            if re.search(pat, doc or ''): bad=True
        if not bad: out.append(r)
    return out

def aggregate_count_total_guard(doc: str) -> bool:
    """True for prose such as '1151 lekarzy; łączna kwota ...', not individual lists."""
    t=norm_space(doc)
    count=bool(re.search(r'(?i)(?:ilo[śs][ćc]|liczba)\s+(?:zatrudnionych\s+)?lekarzy.{0,80}?\b\d{1,5}\s*(?:os[oó]b)?', t))
    total=bool(re.search(r'(?i)(?:[łl][ąa]czna|sumaryczna|suma)\s+(?:kwota\s+)?(?:wyp[łl]aconych\s+)?wynagrodze[nń].{0,100}?\d{1,3}(?:[ .]\d{3})+', t))
    return count and total

def is_correction_message(text: str) -> bool:
    """Parse or process the `is_correction_message` layout/stage."""
    t = text or ''
    # "prawo do sprostowania danych" w stopce RODO nie jest korektą odpowiedzi.
    t_wo_rodo = re.sub(
        r'(?is)prawo.{0,80}sprostowan.{0,120}(?:danych|osobow)',
        ' ',
        t
    )
    correction = r'(?:korekt\w*|skorygow\w*|poprawion\w*|sprostowan\w*)'
    salary_ctx = r'(?:wynagrodze[nń]|kwot|tabel|wykaz|zestaw|lekarz)'
    explicit = bool(
        re.search(rf'(?is){correction}.{{0,260}}{salary_ctx}', t_wo_rodo)
        or re.search(rf'(?is){salary_ctx}.{{0,260}}{correction}', t_wo_rodo)
        or re.search(r'(?is)b[łl][ąa]d\w*.{0,180}(?:ksi[eę]gow|kwot|wykaz|zestaw|wynagrod)', t_wo_rodo)
        or re.search(r'(?is)omy[łl]k\w*.{0,180}(?:kwot|wykaz|zestaw|wynagrod)', t_wo_rodo)
    )
    return explicit

def prefer_latest_correction(doc: str) -> str:
    """If later recipient material is explicitly a correction, discard earlier salary versions."""
    parts=re.split(r'(?m)(?=^### WIADOMOŚĆ ODBIORCY\s*$)', doc or '')
    parts=[x for x in parts if x.strip()]
    corr=[i for i,x in enumerate(parts) if is_correction_message(x)]
    if corr:
        part=parts[corr[-1]]
        # Within that message, keep the salary table nearest before the correction note.
        ms=list(re.finditer(r'(?i)\b(?:korekt\w*|skorygow\w*|poprawion\w*|sprostowan\w*)\b', part))
        if ms:
            pos=ms[-1].start()
            anchors=[m.start() for m in re.finditer(r'(?m)^# \*\*Tabela\s+1\*\*\s*$', part[:pos])]
            if anchors:
                part=part[max(anchors):]
        return part
    return doc

def is_wrong_month(text: str) -> bool:
    """Parse or process the `is_wrong_month` layout/stage."""
    return bool(re.search('(?i)(?:stycze[nń]|luty|marzec|kwiecie[nń]|maj|czerwiec|lipiec|sierpie[nń]|wrzesie[nń]|październik|pazdziernik|listopad|grudzie[nń]).{0,40}\\b(?:2024|2026|2027)\\b', text))

def recipient_document(full_doc: str) -> tuple[str, dict]:
    """Build the parser input document from recipient-side correspondence only."""
    doc, meta = extract_recipient_messages(full_doc)
    if len(money_cells(doc)) >= 10 or not re.search('(?m)^A\\) email jest odpowiedzią', full_doc):
        return (prefer_latest_correction(doc), meta)
    candidates = []
    for ch in re.split('(?m)^### WIADOMOŚĆ ODBIORCY\\s*$', full_doc)[1:]:
        if not re.search('(?m)^A\\) email jest odpowiedzią', ch):
            continue
        ch = re.split('(?m)^Znormalizowana odpowiedź\\s*$', ch, maxsplit=1)[0]
        if money_cells(ch) and (not is_wrong_month(ch)):
            candidates.append(ch)
    if not candidates:
        for m in re.finditer('(?m)^A\\) email jest odpowiedzią', full_doc):
            begin = max(0, full_doc.rfind('### WIADOMOŚĆ ODBIORCY', 0, m.start()))
            finish = full_doc.find('Znormalizowana odpowiedź', m.end())
            ch = full_doc[begin:finish if finish >= 0 else len(full_doc)]
            if len(money_cells(ch)) >= 5 and (not is_wrong_month(ch)):
                candidates.append(ch)
    if candidates:
        doc = max(candidates, key=lambda x: len(money_cells(x)))
        meta.update(thread_detected=True, substantive_recipient_messages=1, fallback_a_message=True)
    doc = prefer_latest_correction(doc)
    return (doc, meta)

def page_is_group_aggregate_salary_table(page: str) -> bool:
    """Parse or process the `page_is_group_aggregate_salary_table` layout/stage."""
    lines = page.splitlines()
    for i, line in enumerate(lines[:-1]):
        headers = split_markdown_row(line)
        sep = split_markdown_row(lines[i + 1])
        if len(headers) < 2 or len(sep) != len(headers) or not is_separator_row(sep):
            continue
        h = ' '.join((clean_header(x) for x in headers))
        if (re.search(r'(?i)liczba\s+lekarzy|liczba\s+osób|liczba\s+osob', h)
                and re.search(r'(?i)łączna\s+kwota\s+wynagrodze[nń]|laczna\s+kwota\s+wynagrodze[nń]|suma\s+wynagrodze[nń]', h)):
            return True
    return False

