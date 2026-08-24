# fedrowanie-parser

Parser odpowiedzi placówek medycznych dotyczących wynagrodzeń lekarzy za 2025 r.

Repozytorium zawiera aktualną wersję parsera **v35**, rozbitą na główny parser i wyspecjalizowane moduły kontekstowe. Projekt jest przygotowany do uruchamiania przez **Poetry**.

## Co parser wyciąga

Tabela wynikowa zawiera m.in.:

- identyfikator sprawy i placówki,
- techniczną nazwę rekordu,
- **imię i nazwisko**,
- **inicjały** (gdy placówka anonimizuje lekarzy),
- **specjalizację**,
- **stanowisko/status**,
- **jednostkę/oddział**,
- **typ umowy**,
- wynagrodzenie netto i brutto,
- stronę, użyty parser, poziom pewności, surowy wiersz i komentarz.

Parser obsługuje również szczególne formaty, które pojawiały się w danych: miesięczne zestawienia wymagające agregacji do roku, wielokolumnowe formy zatrudnienia, informacje o umowie z kontekstu załącznika, specjalizacje i oddziały wynikające z układu dokumentu oraz anonimizację za pomocą inicjałów.

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

4. **Normalizacja do wspólnego modelu.** Niezależnie od formatu wejściowego każdy zaakceptowany rekord jest sprowadzany do `SalaryRow`, czyli wspólnego modelu zawierającego m.in. kwotę, typ umowy, specjalizację, jednostkę/oddział, imię i nazwisko, inicjały oraz stanowisko/status.

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

## Struktura

```text
fedrowanie-parser/
├── pyproject.toml
├── README.md
├── .gitignore
├── LICENSE
├── data/
│   └── README.md
├── output/
│   └── .gitkeep
├── src/
│   └── fedrowanie_parser/
│       ├── __init__.py
│       ├── cli.py
│       ├── attachment_contract_context.py
│       ├── contract_semantic_context.py
│       ├── doctor_initials_context.py
│       ├── doctor_status_context.py
│       ├── monthly_ledger_annualizer_v2_local_fuzzy.py
│       ├── multi_contract_columns.py
│       ├── organizational_unit_context.py
│       ├── person_name_context.py
│       ├── section_salary_list.py
│       ├── specialization_context.py
│       └── unit_column_context.py
└── tests/
    └── test_smoke.py
```

## Wymagania

- Python 3.11+
- Poetry

Kod parsera korzysta wyłącznie z biblioteki standardowej Pythona. `pytest` jest zależnością developerską do testów.

## Instalacja

```bash
git clone <URL_REPOZYTORIUM>
cd fedrowanie-parser
poetry install
```

## Uruchomienie

Umieść wejściową bazę SQLite lokalnie, np. jako:

```text
data/fedrowanie.db
```

Następnie:

```bash
poetry run fedrowanie-parser data/fedrowanie.db \
  --out-db output/fedrowanie_wynagrodzenia_2025.db \
  --rows-csv output/wynagrodzenia_lekarzy_2025.csv \
  --summary-csv output/podsumowanie_placowek_2025.csv
```

Można też uruchomić moduł bezpośrednio:

```bash
poetry run python -m fedrowanie_parser.cli data/fedrowanie.db
```

Parser kopiuje wejściową bazę do `--out-db`, a następnie tworzy/odświeża w niej tabele `salaries_extracted` i `salaries_summary`. Generuje też dwa pliki CSV.

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
