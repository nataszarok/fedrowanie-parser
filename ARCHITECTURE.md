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
