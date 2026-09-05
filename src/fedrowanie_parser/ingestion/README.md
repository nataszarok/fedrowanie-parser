# Generic ingestion

`fedrowanie-ingest` is a staging importer for heterogeneous salary documents (`pdf`, `xls`, `xlsx`, `ods`, `docx`). It intentionally does **not** insert directly into `salaries_extracted`.

The production flow is:

```text
source files
  -> fedrowanie-ingest
  -> ingestion_documents + ingestion_rows
  -> fedrowanie-review
  -> fedrowanie-promote --dry-run
  -> fedrowanie-promote --commit
  -> salaries_extracted
```


## 0. Check runtime dependencies

Before the first import, especially on macOS, run:

```bash
fedrowanie-ingest --check-deps
```

Legacy `.xls` files require LibreOffice. Scanned/image-only PDFs require Tesseract OCR.
On macOS the usual installation is:

```bash
brew install --cask libreoffice
brew install tesseract
# optional but recommended for Polish/Latin OCR:
brew install tesseract-lang
```

The importer also discovers the standard macOS LibreOffice app path
`/Applications/LibreOffice.app/Contents/MacOS/soffice`, so LibreOffice does not
have to expose a `soffice` command on `PATH`. For OCR it prefers `Latin`, then
`pol+eng`, `pol`, and finally `eng` if those language packs are available. If a
scanned PDF needs OCR but Tesseract is missing, the document is now reported as
`ERROR` with an explicit dependency message rather than the misleading
`NO_TABLES`/`NO_ROWS`.

## 1. Parse into staging

```bash
fedrowanie-ingest \
  --db fedrowanie_wynagrodzenia_2025.db \
  --input ./watch_dog \
  --report ingestion_report.md
```

`--input` points to an unpacked directory. The importer skips `__MACOSX`, `._*` and Office lock files (`~$*`).

`ingestion_documents` stores one row per source document, parser/control status and human-review state. `ingestion_rows` stores the extracted salary records. Re-running an unchanged document preserves its review decision. If semantic staging output changes, review is reset to `PENDING`.

## 2. Review

List staged documents:

```bash
fedrowanie-review --db fedrowanie_wynagrodzenia_2025.db --list
```

Approve a single source (full path, basename, or unique filename fragment):

```bash
fedrowanie-review \
  --db fedrowanie_wynagrodzenia_2025.db \
  --approve "SPZOZ_Kościan.pdf" \
  --note "verified against source"
```

You can also use `--reject`, `--pending`, or `--approve-all-ok`. `--approve-all-ok` is a convenience only; manual review remains the safer workflow when OCR was involved.

## 3. Promotion dry-run

Dry-run is the default and makes no canonical changes:

```bash
fedrowanie-promote --db fedrowanie_wynagrodzenia_2025.db
```

The command prints `INSERT`, `SKIP`, or `BLOCK` for every approved source plus before/projected row counts and compensation totals.

Promotion verifies, per source document:

- staging row count equals `ingestion_documents.accepted_rows`,
- staging gross sum equals `ingestion_documents.gross_sum`,
- staging fingerprint is unchanged since review,
- the same source has not already been promoted,
- the staged institution does not already have rows in `salaries_extracted`,
- the canonical insert changes row count and compensation sum by exactly the expected values.

## 4. Commit approved documents

```bash
fedrowanie-promote \
  --db fedrowanie_wynagrodzenia_2025.db \
  --commit
```

Before `--commit`, promotion also checks whether the staged institution already exists in `salaries_extracted`. A match by `institution_pk`, or by an exactly normalized institution name when no PK is available, is shown as `BLOCK` and the commit exits without inserting anything. This protects against accidentally importing the same hospital/facility twice.

If you reviewed the collision and intentionally want to append another document for an institution that already exists, opt in explicitly:

```bash
fedrowanie-promote \
  --db fedrowanie_wynagrodzenia_2025.db \
  --commit \
  --allow-existing-institution
```

Each source document is promoted in its own atomic transaction. Promotion adds provenance columns to `salaries_extracted` when needed:

- `ingestion_source_file`
- `ingestion_source_locator`
- `ingestion_fingerprint`
- `ingestion_promotion_id`

This makes imports idempotent and reversible.

To promote only selected approved files:

```bash
fedrowanie-promote \
  --db fedrowanie_wynagrodzenia_2025.db \
  --source "Kościan" \
  --source "Otwock" \
  --commit
```

## 5. Rollback

```bash
fedrowanie-promote \
  --db fedrowanie_wynagrodzenia_2025.db \
  --rollback "Kościan"
```

Rollback first verifies the exact promoted row count and compensation sum, then removes only rows linked to that promotion id.

## OCR notes

PDF handling still prefers native text and PyMuPDF table geometry. OCR is used only for image-only pages. For scanned grid-style salary tables, the OCR fallback combines two layout modes and uses the right-side amount column to prevent LP/index digits from being glued to compensation amounts. This is the regression that fixes the Wilkowice case while preserving the earlier Kościan and Sulęcin behavior.
