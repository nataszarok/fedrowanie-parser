
from __future__ import annotations
import re

def _norm(s):
    return re.sub(r'\s+',' ',str(s or '').replace('\xa0',' ')).strip(' |#*_-–—:\t\r\n')

# Ordered from more specific to more generic.
PATTERNS = [
    ("radiologia i diagnostyka obrazowa", re.compile(r'(?i)\bradiologia\s+i\s+diagnostyka\s+obrazowa\b')),
    ("radiologia", re.compile(r'(?i)\bradiolog(?:ia|ii|icz\w*|a|iem)?\b|\bradiodiagnost\w*\b')),
    ("psychiatria dzieci i młodzieży", re.compile(r'(?i)\bpsychiatri\w+\s+dzieci\s+i\s+m[łl]odzie[żz]y\b')),
    ("psychiatria", re.compile(r'(?i)\bpsychiatr\w*\b')),
    ("anestezjologia i intensywna terapia", re.compile(r'(?i)\banestezjolog\w*(?:\s+i\s+intensywn\w+\s+terapi\w*)?\b')),
    ("neurochirurgia", re.compile(r'(?i)\bneurochirurg\w*\b')),
    ("hematologia", re.compile(r'(?i)\bhematolog\w*\b')),
    ("chirurgia klatki piersiowej", re.compile(r'(?i)\bchirurg\w+\s+klatki\s+piersiow\w*\b')),
    ("chirurgia naczyniowa", re.compile(r'(?i)\bchirurg\w+\s+naczyniow\w*\b')),
    ("chirurgia ogólna", re.compile(r'(?i)\bchirurg\w+\s+og[oó]ln\w*\b')),
    ("chirurgia", re.compile(r'(?i)\bchirurg\w*\b')),
    ("kardiochirurgia", re.compile(r'(?i)\bkardiochirurg\w*\b')),
    ("kardiologia", re.compile(r'(?i)\bkardiolog\w*\b')),
    ("nefrologia", re.compile(r'(?i)\bnefrolog\w*\b')),
    ("neurologia", re.compile(r'(?i)\bneurolog\w*\b')),
    ("urologia", re.compile(r'(?i)\burolog\w*\b')),
    ("okulistyka", re.compile(r'(?i)\bokulist\w*\b')),
    ("otolaryngologia", re.compile(r'(?i)\botolaryngolog\w*|\blaryngolog\w*\b')),
    ("pediatria", re.compile(r'(?i)\bpediatr\w*\b')),
    ("ginekologia i położnictwo", re.compile(r'(?i)\b(?:ginekolog\w*.{0,20}po[łl]o[żz]nictw\w*|po[łl]o[żz]nictw\w*.{0,20}ginekolog\w*)\b')),
    ("ginekologia", re.compile(r'(?i)\bginekolog\w*\b')),
    ("choroby wewnętrzne", re.compile(r'(?i)\bchor[oó]b\w+\s+wewn[ęe]trzn\w*|\binternist\w*\b')),
    ("medycyna rodzinna", re.compile(r'(?i)\bmedycyn\w+\s+rodzinn\w*\b')),
    ("rehabilitacja medyczna", re.compile(r'(?i)\brehabilitacj\w+\s+medyczn\w*\b')),
    ("rehabilitacja", re.compile(r'(?i)\brehabilitacj\w*\b')),
    ("medycyna ratunkowa", re.compile(r'(?i)\bmedycyn\w+\s+ratunkow\w*\b')),
    ("onkologia kliniczna", re.compile(r'(?i)\bonkolog\w+\s+kliniczn\w*\b')),
    ("onkologia", re.compile(r'(?i)\bonkolog\w*\b')),
    ("pulmonologia", re.compile(r'(?i)\bpulmonolog\w*\b|\bchor[oó]b\w+\s+p[łl]uc\b')),
    ("dermatologia", re.compile(r'(?i)\bdermatolog\w*\b')),
    ("endokrynologia", re.compile(r'(?i)\bendokrynolog\w*\b')),
    ("ortopedia i traumatologia", re.compile(r'(?i)\bortoped\w*.{0,30}traumatolog\w*|\btraumatolog\w*.{0,30}ortoped\w*')),
    ("ortopedia", re.compile(r'(?i)\bortoped\w*\b')),
    ("medycyna paliatywna", re.compile(r'(?i)\bmedycyn\w+\s+paliatywn\w*\b')),
]

GENERIC_ONLY = re.compile(
    r'(?i)^(?:lekarz\s+)?(?:specjalista|lekarz specjalista|'
    r'lekarz w trakcie specjalizacji|lekarz bez specjalizacji)$'
)

def _clean_candidate(raw):
    s=_norm(raw)
    # Remove obvious amount fragments / index cells, keep wording.
    s=re.sub(r'\b\d{1,3}(?:[ .]\d{3})*[,.]\d{2}\s*(?:z[łl]|pln)?\b',' ',s,flags=re.I)
    s=re.sub(r'^\s*\d+\s*\|\s*','',s)
    return _norm(s)

def infer_specialization_from_raw_row(raw_row, existing_spec='', organizational_unit=''):
    """
    Conservative record-level specialization extraction.
    Existing non-empty specialization always wins.
    Returns (specialization, evidence) or None.
    """
    existing=_norm(existing_spec)
    role_only=False
    # Roles/functions are not medical specialties.
    if existing and re.fullmatch(
        r'(?i)(?:lekarz\s+)?(?:asystent(?:\s+oddzia[łl]u)?|'
        r'kierownik(?:\s+oddzia[łl]u)?|koordynator|'
        r'zast[ęe]pca\s+(?:koordynatora|ordynatora)|z-ca\s+(?:koordynatora|ordynatora)|'
        r'ordynator|rezydent|lekarz medycyny)',
        existing
    ):
        existing=''
        role_only=True
    if existing:
        return None

    unit=_norm(organizational_unit)

    raw=_clean_candidate(raw_row)
    if not raw:
        return None

    # Evaluate text cells separately. A cell explicitly describing an
    # organizational unit must not create a physician specialty.
    cells=[_norm(x) for x in str(raw_row or '').strip().strip('|').split('|')]
    unit_cell_re=re.compile(
        r'(?i)(?:\b(?:oddzia[łl]|pododdzia[łl]|klinika|pracownia|poradnia|zak[łl]ad|'
        r'szpitalny oddzia[łl] ratunkowy|SOR\b|izba przyj[ęe][ćc]|o[śs]rodek)\b|'
        r'^\s*kl\.\s*|^\s*o\.\s*)'
    )
    candidate_cells=[]
    for c in cells:
        if not c:
            continue
        # A structurally identified organizational-unit cell can describe the
        # specialty of the clinic without proving the doctor's specialization.
        if unit and _norm(c).casefold()==unit.casefold():
            continue
        if unit_cell_re.search(c):
            continue
        # Skip pure index / money / contract cells.
        if re.fullmatch(r'\d+',c):
            continue
        if re.search(r'\d{1,3}(?:[ .]\d{3})*[,.]\d{2}',c):
            continue
        if re.fullmatch(r'(?i)(?:umowa zlecenia|umowa o prac[ęe]|kontrakt|cywilnoprawna)',c):
            continue
        candidate_cells.append(c)

    # For structured table rows, excluded cells stay excluded. Falling back
    # to the whole row would re-import unit names such as "Poradnia Ginekologiczna".
    # Whole-row fallback is allowed only for unstructured/plain-text records.
    if candidate_cells:
        search_text=' | '.join(candidate_cells)
    elif len(cells)<=1:
        search_text=raw
    else:
        return None
    hits=[]
    for label,pat in PATTERNS:
        if pat.search(search_text):
            hits.append(label)

    # Deduplicate nested labels.
    cleaned=[]
    for h in hits:
        if h=="radiologia" and "radiologia i diagnostyka obrazowa" in hits:
            continue
        if h=="psychiatria" and "psychiatria dzieci i młodzieży" in hits:
            continue
        if h=="anestezjologia" and "anestezjologia i intensywna terapia" in hits:
            continue
        if h=="chirurgia" and any(x.startswith("chirurgia ") for x in hits):
            continue
        if h=="rehabilitacja" and "rehabilitacja medyczna" in hits:
            continue
        if h=="onkologia" and "onkologia kliniczna" in hits:
            continue
        if h=="ortopedia" and "ortopedia i traumatologia" in hits:
            continue
        if h=="ginekologia" and "ginekologia i położnictwo" in hits:
            continue
        cleaned.append(h)
    hits=list(dict.fromkeys(cleaned))

    if not hits:
        if role_only:
            return '', "usunięto rolę/funkcję z pola specjalizacja"
        return None

    # Prefer a concise canonical label. If two independent specialties are
    # explicitly present, preserve both.
    if len(hits)==1:
        spec=hits[0]
    else:
        # Preserve at most two strong explicit specialties.
        spec=" / ".join(hits[:2])
    return spec, f"specjalizacja z raw_row: {spec}"
