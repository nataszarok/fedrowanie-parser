# fedrowanie-parser

Parser odpowiedzi placówek medycznych dotyczących wynagrodzeń lekarzy za 2025 r.

Repozytorium zawiera aktualną wersję parsera **v35**, rozbitą na główny parser i wyspecjalizowane moduły kontekstowe. Projekt jest przygotowany do uruchamiania przez **Poetry**.

## Przykładowy wynik

Po parsowaniu dane są normalizowane do jednej tabeli. Przykładowe, zanonimizowane wiersze mogą wyglądać tak:

| placówka | imię i nazwisko | inicjały | specjalizacja | stanowisko/status | jednostka/oddział | typ umowy | wynagrodzenie brutto |
|---|---|---|---|---|---|---|---:|
| Szpital A | Jan Kowalski |  | radiologia i diagnostyka obrazowa | lekarz specjalista | Zakład Diagnostyki Obrazowej | kontrakt | 1 245 300,00 zł |
| Szpital B |  | A.B. | choroby wewnętrzne | starszy asystent | Oddział Chorób Wewnętrznych | umowa o pracę | 684 250,40 zł |
| Szpital C | Anna Nowak |  |  | lekarz w trakcie specjalizacji | SOR | umowa zlecenia | 312 800,00 zł |
| Szpital D |  | K.M. | anestezjologia i intensywna terapia | lekarz specjalista | OAiIT |  | 958 410,75 zł |

To tylko przykład struktury wyniku — wartości i dane osobowe w tabeli powyżej są przykładowe. W rzeczywistych danych część pól może być pusta, jeżeli placówka nie podała danej informacji albo nie da się jej wiarygodnie wywnioskować z dokumentu.

Oprócz pól pokazanych wyżej wynik zawiera także identyfikatory sprawy i placówki, kwotę netto, numer strony, nazwę użytego parsera, poziom pewności, surowy wiersz źródłowy i komentarz techniczny.

## Szybki start — jak wygenerować bazę

Projekt wymaga **Python 3.11+** i **Poetry**. Po sklonowaniu lub rozpakowaniu repozytorium wejdź do jego katalogu i zainstaluj projekt:

```bash
poetry env use python3.11   # opcjonalnie, jeśli domyślny Python jest starszy niż 3.11
poetry install
```

Następnie uruchom parser, podając ścieżkę do źródłowej bazy `fedrowanie.db`:

```bash
poetry run fedrowanie-parser /sciezka/do/fedrowanie.db
```

Przykład, jeśli baza znajduje się w sąsiednim repozytorium:

```bash
poetry run fedrowanie-parser ../fedrowanie/data/fedrowanie.db
```

Można też uruchomić ten sam kod jako moduł Pythona:

```bash
poetry run python -m fedrowanie_parser.cli ../fedrowanie/data/fedrowanie.db
```

Bez dodatkowych argumentów parser zapisze wyniki w bieżącym katalogu zgodnie z domyślnymi nazwami CLI. Jeśli chcesz jawnie kontrolować lokalizację wszystkich wyników:

```bash
mkdir -p output

poetry run fedrowanie-parser ../fedrowanie/data/fedrowanie.db \
  --out-db output/fedrowanie_wynagrodzenia_2025.db \
  --rows-csv output/wynagrodzenia_lekarzy_2025.csv \
  --summary-csv output/podsumowanie_placowek_2025.csv
```

Najważniejszym artefaktem jest `--out-db`: jest to wynikowa baza SQLite zawierająca wyparsowane dane. Dwa pliki CSV są wygodnymi eksportami tabeli szczegółowej i podsumowania.

> Samo `poetry run ...` na świeżo pobranym repozytorium nie wystarczy. Najpierw wykonaj `poetry install`, aby pakiet `fedrowanie_parser` został zainstalowany w środowisku Poetry.

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

## Instalacja

Pełny przykład uruchomienia znajduje się w sekcji **Szybki start** na początku README.

```bash
git clone <URL_REPOZYTORIUM>
cd fedrowanie-parser
poetry env use python3.11   # opcjonalnie
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
