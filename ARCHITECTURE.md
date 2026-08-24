# Architecture

The package is grouped by responsibility rather than institution.

## Packages

- `parsing/` — converts source layouts into `SalaryRow` candidates:
  `tables.py`, `layouts.py`, `plain_text.py`.
- `enrichment/` — derives semantic fields from context: names, initials,
  doctor status, specialization, organizational unit and contract information.
- `processing/` — document-level mechanics and shared normalization.
- `special_cases/` — materially different algorithms such as monthly-ledger
  annualization, multi-contract columns and section salary lists.
- `io/` — persistence only.

## Top level

- `pipeline.py` orchestrates extraction.
- `cli.py` only wires command-line execution.
- `models.py` defines `SalaryRow`.
- `constants.py` contains shared constants and compiled regexes.

```text
cli
 └─> pipeline
      ├─> processing
      ├─> parsing
      ├─> enrichment
      ├─> special_cases
      └─> io

models + constants are shared foundations
```

New rules should be generic and placed according to responsibility/layout.
Institution-specific fixes are a last resort.
