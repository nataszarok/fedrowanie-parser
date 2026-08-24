"""Public special-case parser API used by the extraction pipeline."""

from .monthly_ledger import (
    parse_money_pl,
    clean_entity,
    canonical_entity,
    display_choice,
    classify_entity,
    parse_monthly_ledger,
    merge_local_person_variants,
    aggregate_transactions,
    aggregate_monthly_ledger,
    near_duplicate_candidates,
    read_case_text,
    write_csv,
    main,
)

from .multi_contract_columns import (
    contract_type_from_header,
    contract_amount_columns,
    infer_contract_from_multi_columns,
    split_multi_contract_amounts,
    expand_stacked_contract_headers,
    document_multi_contract_row_map,
)

from .section_salary_list import (
    parse_section_salary_list,
)

__all__ = [
    "parse_money_pl",
    "clean_entity",
    "canonical_entity",
    "display_choice",
    "classify_entity",
    "parse_monthly_ledger",
    "merge_local_person_variants",
    "aggregate_transactions",
    "aggregate_monthly_ledger",
    "near_duplicate_candidates",
    "read_case_text",
    "write_csv",
    "main",
    "contract_type_from_header",
    "contract_amount_columns",
    "infer_contract_from_multi_columns",
    "split_multi_contract_amounts",
    "expand_stacked_contract_headers",
    "document_multi_contract_row_map",
    "parse_section_salary_list",
]
