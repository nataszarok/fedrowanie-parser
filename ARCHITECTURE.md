# Architecture

The project is organized around responsibilities and parser families.

## Top-level application layer

- `cli.py` — argument parsing and application wiring only.
- `pipeline.py` — orchestration of document extraction and enrichment.
- `models.py` — core `SalaryRow` data model.
- `constants.py` — project-wide constants and compiled regular expressions.
- `services/` — application-service boundaries used by the pipeline.

## `processing/`

Cross-cutting document mechanics:

- `document.py` — recipient-message selection, page/document filtering, response classification.
- `normalization.py` — money parsing, normalization, shared parsing primitives.

## `parsing/`

Parsers are grouped by **layout family**, not by institution.

- `tables.py` — generic structured Markdown/OCR tables.
- `plain_text.py` — plain-text/stateful fallbacks.
- `structured/continuations.py` — indexed tables, continuation pages and related schemas.
- `sequences/vertical.py` — vertical lists and parallel sequences.
- `sequences/inline.py` — inline numbered/prose salary sequences.
- `ocr/damaged.py` — parsers that explicitly compensate for OCR damage.
- `layouts.py` — compatibility facade exporting the parser families above.

## `enrichment/`

Adds semantic information without creating duplicate salary facts:

- person names and initials,
- doctor status,
- specialization,
- organizational unit,
- contract context.

## `special_cases/`

Algorithms that are materially different from ordinary row parsing:

- monthly-ledger annualization,
- multi-contract-column interpretation,
- section salary lists.

## `io/`

Persistence only. No parsing rules.

## Dependency direction

```text
cli
 |
 v
pipeline ---> services
 |   |   +--> processing
 |   +--> parsing
 |   +--> enrichment
 |   +--> special_cases
 |
 +------> io

models + constants = shared foundations
```

## Refactoring principles

1. Parser rules are generic and layout-driven whenever possible.
2. `cli.py` contains no extraction logic.
3. Persistence is isolated from parsing.
4. Enrichment must not silently create duplicate salary facts.
5. Every substantial structural refactor must pass a full regression against the
   previous version: row count, institution count, total amounts and exact
   semantic output after stable sorting.

## Module API conventions

Public API is intentionally visible at the top of implementation modules.

- Functions imported by another module are public and do not use a leading `_`.
- A leading `_` means a helper is private to its own module.
- Public functions are defined before private implementation helpers.
- Key modules declare `__all__` to make their supported API explicit.
- Cross-module imports of private helpers are prohibited.
- Shared behavior belongs in a shared module rather than being imported as a
  private implementation detail from an unrelated module.

## Readability conventions

- Multi-line SQL is written as triple-quoted strings, not escaped `\n` literals.
- Public functions have short docstrings that describe purpose and return behavior.
- Docstrings avoid repeating parameter names when the signature is already self-explanatory.
- Longer docstrings are reserved for non-obvious parsing assumptions or activation guards.

- no undefined global dependencies hidden by transitive imports,

## Public API facades

`pipeline.py` imports complete public APIs from small facade modules. Wildcard
imports are allowed there only because every imported module defines an explicit
`__all__`; this keeps the pipeline import section readable while preserving a
strict public/private boundary.

Constants are always imported explicitly by name. This improves static analysis
and IDE support (e.g. VS Code/Pylance) and avoids hidden dependencies.

## Source repository boundary

`pipeline.py` does not know the SQLite source schema. The `io/source_repository.py`
module owns the join across `case_pages`, `cases`, and `institutions`, assembles
`SourceCase` objects, and persists case-level diagnostics.

The pipeline operates only on domain models (`SourceCase`, `SalaryRow`,
`CaseParseStatus`, `ExtractionResult`). This keeps SQL and database-schema
knowledge out of extraction logic.

## Output persistence flow

The CLI exposes the three SQLite outputs explicitly:

```text
ExtractionResult.statuses -> write_case_statuses() -> cases_status

ExtractionResult.rows -> write_extracted_rows() -> salaries_extracted
salaries_extracted -> write_summary() -> salaries_summary

cases_status -> write_case_status_csv()
salaries_extracted -> write_extracted_csv()
salaries_summary -> write_summary_csv()
```

`source_repository.py` is read-only and only assembles `SourceCase` objects.
`storage.py` owns all writes and each public function performs one visible output step.

## Unprocessed attachment diagnostics

`source_repository.load_source_cases()` checks attachment metadata for potentially
data-bearing formats (`xls`, `xlsx`, `ods`, `zip`, `7z`, `dat`, `rar`, `doc`, `docx`).
An attachment is considered unprocessed when no matching non-empty record exists
in `attachment_texts`.

The information is carried by `SourceCase.unprocessed_attachments` and persisted exclusively as the `unprocessed_attachment` flag in `cases_status`.
The semantic `status` remains independent from attachment-processing diagnostics.

## Procedural case flags

Procedural correspondence signals are modeled independently from the final
semantic case status. `processing/case_flags.py` classifies recipient-side
correspondence into boolean `CaseFlags`, which are persisted as columns in
`cases_status`. This allows one case to retain multiple events (for example,
deadline extension followed by a successful data response) without turning
`status` into a mutually-exclusive workflow state machine.

## Segment-level numbered-series reconciliation

A case may contain one logical numbered salary list represented by multiple OCR
layouts. The pipeline therefore parses pages/sections normally and treats the
full-document `vertical-index-amount-series` result as an additional structured
segment rather than an authoritative replacement for the whole case.

`_reconcile_numbered_annual_series()` merges candidates by logical `Lekarz N`
index. Structured segment rows win only inside the range they cover; rows from
other parsers are retained outside that range. Reconciliation activates only
when the combined candidates form a complete sequence from 1 through the end of
the structured segment.

## Typ odbiorcy i podsumowania

`SalaryRow` zachowuje wszystkie ujawnione kwoty, także gdy odbiorcą jest spółka.
Pola `recipient_type` i `recipient_name` rozdzielają rekordy lekarzy od rekordów
podmiotów zbiorczych. `salaries_summary` nie filtruje rekordów globalnym `WHERE`;
zawiera metryki ogólne oraz osobne grupy `doctor_*` i `company_*`. Dzięki temu
łączna wartość ujawnionych świadczeń pozostaje dostępna, a statystyki indywidualnych
wynagrodzeń lekarzy nie obejmują kwot przypisanych spółkom.

