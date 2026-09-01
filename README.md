# fedrowanie-parser

Parser odpowiedzi placówek medycznych dotyczących wynagrodzeń lekarzy za 2025 r.

Parser **nie pobiera danych źródłowych samodzielnie**. Jego wejściem jest baza SQLite
`fedrowanie.db` generowana przez osobne repozytorium
`zarobkilekarzy/fedrowanie`:

https://github.com/zarobkilekarzy/fedrowanie/tree/main

Pełny przepływ danych wygląda więc następująco:

```text
zarobkilekarzy/fedrowanie
        │
        │ pobranie i przetworzenie danych źródłowych
        ▼
data/fedrowanie.db
        │
        │ wejście do tego projektu
        ▼
fedrowanie-parser
        │
        ├── cases_status
        ├── salaries_extracted
        └── salaries_summary
```

Repozytorium `fedrowanie` jest źródłem danych i odpowiada za utworzenie oraz
zasilenie bazy wejściowej. Dopiero gotową bazę `fedrowanie.db` należy przekazać
do tego parsera.

## Szybki start

Do pełnego uruchomienia procesu potrzebne są **oba repozytoria**. Najwygodniej
trzymać je obok siebie:

```text
workspace/
├── fedrowanie/
└── fedrowanie-parser/
```

### 1. Pobierz repozytorium źródłowe

```bash
git clone https://github.com/zarobkilekarzy/fedrowanie.git
cd fedrowanie
```

Następnie przygotuj środowisko i wykonaj komendy opisane w README projektu
`fedrowanie`, które **tworzą i zasilają bazę `data/fedrowanie.db`**.

> `fedrowanie` jest niezależnym projektem i pozostaje właścicielem procesu
> pozyskiwania danych. Dlatego konkretne komendy służące do zasilania bazy
> powinny być brane z jego aktualnego README, zamiast duplikować je tutaj i
> ryzykować, że dokumentacja obu repozytoriów się rozjedzie.

Przed uruchomieniem parsera upewnij się, że istnieje:

```text
fedrowanie/data/fedrowanie.db
```

### 2. Pobierz i zainstaluj parser

Wróć do katalogu nadrzędnego i pobierz to repozytorium:

```bash
cd ..
git clone <URL_REPOZYTORIUM_FEDROWANIE_PARSER>
cd fedrowanie-parser

poetry env use python3.11   # opcjonalnie, jeśli domyślny Python jest starszy
poetry install
```

Projekt wymaga **Python 3.11+** i **Poetry**.

### 3. Uruchom parser na wygenerowanej bazie

Jeżeli oba repozytoria znajdują się obok siebie:

```bash
poetry run fedrowanie-parser ../fedrowanie/data/fedrowanie.db
```

To samo można uruchomić bezpośrednio jako moduł Pythona:

```bash
poetry run python -m fedrowanie_parser.cli ../fedrowanie/data/fedrowanie.db
```

Jeżeli chcesz jawnie wskazać wszystkie pliki wynikowe:

```bash
mkdir -p output

poetry run fedrowanie-parser ../fedrowanie/data/fedrowanie.db \
  --out-db output/fedrowanie_wynagrodzenia_2025.db \
  --case-status-csv output/status_spraw_2025.csv \
  --rows-csv output/wynagrodzenia_lekarzy_2025.csv \
  --summary-csv output/podsumowanie_placowek_2025.csv
```

Parser kopiuje bazę wejściową do `--out-db` i na tej kopii tworzy lub odświeża
trzy tabele wynikowe. **Każda z nich ma również własny eksport CSV.**

| tabela SQLite | zawartość | odpowiednik CSV |
|---|---|---|
| `cases_status` | Jeden wiersz na analizowaną sprawę. Zawiera `case_pk`, placówkę, status parsowania, powód nadania statusu oraz liczbę wykrytych kandydatów na rekordy. Służy do diagnostyki: pokazuje również sprawy, z których finalnie nie wyciągnięto wynagrodzeń. | `status_spraw_2025.csv` |

### Statusy w `cases_status`

Pole `status` opisuje **wynik analizy całej sprawy**, a nie pojedynczego rekordu
wynagrodzenia.

| `status` | znaczenie |
|---|---|
| `INDIVIDUAL_ANNUAL_2025` | Parser rozpoznał indywidualne wynagrodzenia za 2025 r. Rekordy z takiej sprawy mogą trafić do `salaries_extracted`. |
| `INDIVIDUAL_ANNUAL_2025_AFTER_OR_WITH_REFUSAL` | W korespondencji występuje odmowa lub podobne zastrzeżenie, ale mimo tego odpowiedź zawiera indywidualne dane za 2025 r. |
| `SUBSTANTIVE_AGGREGATE_ONLY` | Odpowiedź jest merytoryczna, ale zawiera wyłącznie dane zagregowane/statystyczne zamiast indywidualnych rocznych wynagrodzeń. |
| `SUBSTANTIVE_NONCOMPARABLE_DATA` | Odpowiedź zawiera dane dotyczące wynagrodzeń, ale w formie, której nie można wiarygodnie porównać z indywidualnymi rocznymi wynagrodzeniami za 2025 r. |
| `SUBSTANTIVE_DISTRIBUTION_ONLY` | Odpowiedź podaje jedynie rozkład/przedziały/statystyki wynagrodzeń, a nie rekordy indywidualne. |
| `REFUSAL_NO_SUBSTANTIVE_DATA` | Placówka odmówiła udostępnienia danych i parser nie znalazł równocześnie użytecznych indywidualnych danych wynagrodzeniowych. |
| `NO_SUBSTANTIVE_DATA_DETECTED` | Parser nie wykrył odpowiedzi zawierającej dane, które można potraktować jako indywidualne wynagrodzenia za 2025 r. |

Pole `reason` doprecyzowuje, **dlaczego** sprawa otrzymała dany status. Jest to
pole diagnostyczne i może zawierać bardziej szczegółowe wartości, np.
`recipient_thread_not_detected`, `no_substantive_recipient_reply`,
`individual_or_anonymous_values`, `aggregate_or_statistics`,
`group_min_max_not_individual_salaries` lub
`monthly_group_statistics_not_individual_annual_list`. Informacja o nieprzetworzonym załączniku nie zmienia `status` ani `reason`; jest przechowywana wyłącznie w osobnej fladze `unprocessed_attachment`.

`parsed_candidate_rows` oznacza liczbę rekordów-kandydatów znalezionych podczas
parsowania sprawy. Nie należy interpretować tej wartości jako liczby finalnych
rekordów w `salaries_extracted`, ponieważ dalsza klasyfikacja sprawy decyduje,
czy kandydaci zostaną zaakceptowani.


### Flagi proceduralne w `cases_status`

Status końcowy i flagi proceduralne pełnią różne role. `status` opisuje wynik
merytoryczny całej sprawy, natomiast poniższe kolumny typu `0/1` zachowują
informację o tym, **co wydarzyło się w toku korespondencji**. Kilka flag może
być prawdziwych jednocześnie.

| kolumna | znaczenie |
|---|---|
| `requested_more_time` | Placówka poinformowała o przedłużeniu terminu albo potrzebie dodatkowego czasu na przygotowanie odpowiedzi. |
| `asked_about_anonymization` | Placówka zapytała lub poprosiła o potwierdzenie, czy dane mogą zostać przekazane po anonimizacji / bez danych osobowych. |
| `requested_clarification` | Placówka poprosiła o doprecyzowanie, sprecyzowanie lub dodatkowe wyjaśnienie zakresu wniosku. |
| `requested_processed_info_justification` | Placówka zakwalifikowała żądanie jako dotyczące informacji przetworzonej i oczekiwała wykazania szczególnego interesu publicznego lub dodatkowego uzasadnienia. |
| `fee_notice` | W korespondencji pojawiła się informacja o opłacie lub dodatkowych kosztach przygotowania/udostępnienia informacji. |
| `transferred_or_not_competent` | Placówka wskazała brak właściwości/kompetencji albo przekazała sprawę do innego podmiotu. |
| `formal_deficiency_request` | Placówka wezwała do uzupełnienia braków formalnych, np. podpisu, pełnomocnictwa lub samego wniosku. |
| `refusal_detected` | W canonicalnej klasyfikacji sprawy wykryto odmowę udostępnienia danych. Flaga korzysta z tej samej logiki co finalny status, a nie z osobnego luźnego dopasowania tekstowego. |
| `unprocessed_attachment` | Sprawa zawiera potencjalnie istotny załącznik (`xls/xlsx/ods/zip/7z/dat/rar/doc/docx`) bez niepustego tekstu w `attachment_texts`. |

Przykładowo sprawa może zakończyć się statusem
`INDIVIDUAL_ANNUAL_2025`, a jednocześnie mieć
`requested_more_time = 1`. Oznacza to, że placówka najpierw poprosiła o więcej
czasu, ale ostatecznie przekazała dane.

| `salaries_extracted` | Główna tabela szczegółowa. Jeden wiersz odpowiada wyparsowanemu rekordowi wynagrodzenia. Zawiera m.in. placówkę, nazwisko lub inicjały lekarza, specjalizację, status/stanowisko, jednostkę lub oddział, typ umowy, wynagrodzenie netto/brutto, stronę źródłową, użyty parser, confidence oraz `raw_row`. | `wynagrodzenia_lekarzy_2025.csv` |
| `salaries_summary` | Podsumowanie tworzone z `salaries_extracted`, zagregowane na poziomie placówki. Zawiera liczbę rekordów, sumę wynagrodzeń, najwyższe wynagrodzenie oraz liczbę rekordów przekraczających 500 tys. i 1 mln zł. | `podsumowanie_placowek_2025.csv` |

Wyniki są więc dostępne równolegle w dwóch formatach:

```text
fedrowanie_wynagrodzenia_2025.db
├── cases_status
├── salaries_extracted
└── salaries_summary

CSV
├── status_spraw_2025.csv
├── wynagrodzenia_lekarzy_2025.csv
└── podsumowanie_placowek_2025.csv
```

SQLite jest pełnym wynikiem procesu i zachowuje wszystkie trzy tabele w jednej
bazie. CSV są wygodnymi, niezależnymi eksportami tych samych tabel do dalszej
analizy np. w Excelu, Pythonie lub narzędziach BI.

## Przykładowy wynik

Po parsowaniu dane są normalizowane do jednej tabeli. Przykładowe,
zanonimizowane wiersze `salaries_extracted` mogą wyglądać tak:

| institution_name | doctor_name | doctor_initials | specialization | doctor_status | organizational_unit | contract_type | gross_compensation |
|---|---|---|---|---|---|---|---:|
| Szpital A | Jan Kowalski |  | radiologia i diagnostyka obrazowa | lekarz specjalista | Zakład Diagnostyki Obrazowej | kontrakt | 1 245 300,00 zł |
| Szpital B |  | A.B. | choroby wewnętrzne | starszy asystent | Oddział Chorób Wewnętrznych | umowa o pracę | 684 250,40 zł |
| Szpital C | Anna Nowak |  |  | lekarz w trakcie specjalizacji | SOR | umowa zlecenia | 312 800,00 zł |
| Szpital D |  | K.M. | anestezjologia i intensywna terapia | lekarz specjalista | OAiIT |  | 958 410,75 zł |

To tylko przykład struktury wyniku. W rzeczywistych danych część pól może być
pusta, jeżeli placówka nie podała danej informacji albo nie da się jej
wiarygodnie wywnioskować z dokumentu.

## Jak działa parser — high level

Parser działa warstwowo. Najważniejszą zasadą jest to, że **nie traktuje całej zawartości sprawy jako odpowiedzi placówki**.

1. **Wybór właściwej korespondencji.** Z pełnego wątku sprawy parser identyfikuje wiadomości wysłane przez odbiorcę wniosku (placówkę) i buduje dokument roboczy z tych odpowiedzi. Wiadomości wnioskodawcy, cytowane fragmenty wcześniejszej korespondencji i techniczne elementy wątku nie powinny być źródłem rekordów wynagrodzeń.

2. **Ocena dokumentu i stron.** Dokument jest dzielony na strony/fragmenty, a parser sprawdza ich przydatność dla danych za 2025 r. Na tym etapie odrzucane lub oznaczane są m.in. fragmenty dotyczące innych okresów, metadane, korespondencja formalna i treści, które nie wyglądają jak dane wynagrodzeniowe.

3. **Uruchomienie wielu parserów formatów.** Nie istnieje jeden uniwersalny format odpowiedzi szpitali. Dla tego samego dokumentu mogą zostać uruchomione różne rodziny parserów:
   - tabele Markdown/OCR,
   - układy pionowe i listy,
   - rekordy inline,
   - kontynuacje tabel bez powtórzonego nagłówka,
   - tekstowe fallbacki,
   - formaty częściowo uszkodzone przez OCR,
   - wyspecjalizowane formaty wymagające dodatkowej logiki, np. sumowania miesięcy do wartości rocznej.

   Parsery są grupowane według **struktury danych**, a nie według konkretnej placówki. Reguła specyficzna dla jednego szpitala powinna być ostatecznością.

4. **Normalizacja do wspólnego modelu.** Niezależnie od formatu wejściowego każdy zaakceptowany rekord jest sprowadzany do `SalaryRow`, czyli wspólnego modelu zawierającego m.in. kwotę, contract_type, specjalizację, jednostkę/oddział, doctor_name, doctor_initials oraz doctor_status.

5. **Enrichment z kontekstu.** Część informacji nie znajduje się bezpośrednio w wierszu z kwotą. Osobne moduły potrafią odzyskać dane z kontekstu dokumentu, np. z nagłówka sekcji, nazwy oddziału, nagłówka kolumny, nazwy załącznika lub struktury tabeli. Dotyczy to m.in. typu umowy, specjalizacji, jednostki organizacyjnej, nazwiska/inicjałów i statusu lekarza.

6. **Reconciliation, filtry i deduplikacja.** Wyniki różnych parserów są porównywane, filtrowane i deduplikowane. Celem jest zachowanie najlepszego rekordu źródłowego bez wielokrotnego policzenia tej samej kwoty oraz odrzucenie oczywistych false positives, sum kontrolnych i metadanych.

7. **Eksport i agregacja.** Finalne rekordy trafiają do tabeli szczegółowej i CSV. Następnie tworzona jest tabela podsumowująca na poziomie placówki. Baza wejściowa pozostaje źródłem, a wynik zapisywany jest do osobnej bazy wskazanej przez `--out-db`.

### Schemat przepływu

```text
sprawa / pełny wątek
        │
        ▼
odpowiedzi odbiorcy wniosku
        │
        ▼
selekcja dokumentu i stron za 2025
        │
        ▼
┌─────────────────────────────────────┐
│ wiele parserów zależnych od formatu │
│ tables / layout / plain / OCR / ... │
└─────────────────────────────────────┘
        │
        ▼
     SalaryRow
        │
        ▼
enrichment z kontekstu
        │
        ▼
filtry + reconciliation + deduplikacja
        │
        ▼
rekordy szczegółowe + agregacja placówek
        │
        ▼
      SQLite + CSV
```

Szczegóły podziału odpowiedzialności między modułami znajdują się w `ARCHITECTURE.md`.

## Model domenowy

`SalaryRow` używa tych samych angielskich nazw `snake_case` co tabela `salaries_extracted`, m.in. `institution_name`, `source_name`, `doctor_name`, `doctor_initials`, `specialization`, `doctor_status`, `organizational_unit`, `contract_type`, `net_compensation`, `gross_compensation`, `page_number`, `confidence` i `comment`.

## Struktura

```text
src/fedrowanie_parser/
├── cli.py
├── pipeline.py
├── models.py
├── constants.py
├── services/
│   └── case_extraction.py
├── processing/
│   ├── document.py
│   └── normalization.py
├── parsing/
│   ├── tables.py
│   ├── plain_text.py
│   ├── structured/
│   │   └── continuations.py
│   ├── sequences/
│   │   ├── vertical.py
│   │   └── inline.py
│   └── ocr/
│       └── damaged.py
├── enrichment/
├── special_cases/
└── io/
```

Szczegółowy opis odpowiedzialności modułów znajduje się w `ARCHITECTURE.md`.

## Wymagania

- Python 3.11+
- Poetry

Kod parsera korzysta wyłącznie z biblioteki standardowej Pythona. `pytest` jest zależnością developerską do testów.

## Zależności i czyste środowisko

Parser nie ma zewnętrznych zależności runtime. Korzysta wyłącznie z biblioteki
standardowej Pythona 3.11+ oraz modułów znajdujących się w tym repozytorium.

```toml
[tool.poetry.dependencies]
python = ">=3.11,<4.0"
```

Jedyną zależnością developerską jest `pytest`.

Na nowym komputerze:

```bash
poetry env use python3.11
poetry install
poetry run fedrowanie-parser /sciezka/do/fedrowanie.db
```

## Testy

```bash
poetry run pytest
```

Test smoke sprawdza, czy pakiet i wszystkie moduły parsera dają się zaimportować.

## Dane

Bazy `.db`, pliki CSV z wynikami i inne dane robocze są celowo ignorowane przez Git. Repozytorium zawiera **kod**, a nie dane źródłowe lub dane osobowe.

Jeżeli chcesz wersjonować przykładowe dane testowe, używaj wyłącznie małych, zanonimizowanych fixture'ów w `tests/fixtures/`.

## Aktualna wersja

`0.35.0` odpowiada parserowi v35, w którym dodano osobną obsługę inicjałów lekarzy. Przy ostatnim pełnym przebiegu parser zachowywał liczbę **12 344 rekordów z 138 placówek** bez zmiany łącznej sumy wynagrodzeń względem v34.

## Rozwój

Przy dodawaniu nowego formatu preferowany wzorzec to osobny, mały moduł kontekstowy w `src/fedrowanie_parser/`, importowany przez `cli.py`. Dzięki temu szczególne przypadki nie rozrastają głównego parsera bardziej niż to konieczne.

Przed commitem:

```bash
poetry run pytest
poetry run fedrowanie-parser --help
```

## Licencja

W repozytorium znajduje się placeholder `LICENSE`. Przed publikacją na GitHubie wybierz właściwą licencję dla projektu.

### Segmentowe parsowanie numerowanych list

Jedna odpowiedź może zmieniać layout pomiędzy stronami lub sekcjami. Parser nie
zakłada więc, że cały dokument musi być obsługiwany przez jeden parser. Dla
numerowanych list wynagrodzeń (`Lp. -> kwota`) rozpoznane segmenty są scalane
po numerze pozycji. Silniejszy parser strukturalny może przejąć tylko zakres,
który rozpoznał, a wcześniejsze lub późniejsze pozycje odzyskane przez inny
parser pozostają zachowane.

Przykładowo dokument może mieć pozycje `1-12` w układzie inline, a `13-97` w
układzie pionowym. Wynikiem jest jedna logiczna sekwencja `1-97`, bez
duplikowania tych samych numerów.

## Typ odbiorcy i podsumowania

`SalaryRow` zachowuje wszystkie ujawnione kwoty, także gdy odbiorcą jest spółka.
Pola `recipient_type` i `recipient_name` rozdzielają rekordy lekarzy od rekordów
podmiotów zbiorczych. `salaries_summary` nie filtruje rekordów globalnym `WHERE`;
zawiera metryki ogólne oraz osobne grupy `doctor_*` i `company_*`. Dzięki temu
łączna wartość ujawnionych świadczeń pozostaje dostępna, a statystyki indywidualnych
wynagrodzeń lekarzy nie obejmują kwot przypisanych spółkom.

