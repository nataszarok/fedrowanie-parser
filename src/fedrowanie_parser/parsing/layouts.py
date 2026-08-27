"""Compatibility facade for layout parser families.

New code should import from the concrete submodules. This facade keeps the
pipeline readable and preserves backwards-compatible imports during refactors.
"""
from .structured.continuations import (
    page_context_contract,
    parse_indexed_three_col_continuation,
    parse_indexed_single_salary_markdown,
    parse_indexed_total_gross_continuation,
    parse_salary_bracket_index_table,
    parse_parallel_index_amount_columns,
    parse_vertical_idx_code_gross_net,
)
from .sequences.vertical import (
    parse_vertical_label_amount_pairs,
    parse_vertical_indexname_amount,
    parse_vertical_index_code_label_amount,
    parse_vertical_named_salary_table,
    parse_vertical_role_named_amount,
    parse_two_section_vertical_salary,
    parse_numbered_amount_only_series,
    parse_vertical_index_amount_series,
    parse_parallel_name_amount_lists,
    parse_parallel_doctor_amount_lists,
    parse_anonymous_amount_only_series,
)
from .sequences.inline import (
    parse_numbered_named_inline_salary,
    parse_lekarz_inline_salary,
    parse_embedded_numbered_salary_list,
    parse_specialty_amount_lines,
    parse_explicit_annual_prose_salary,
    parse_body_lekarz_number_amount,
    parse_body_lp_amount,
    parse_annual_amount_contract_lines,
    parse_contract_practice_cost_list,
    parse_single_anonymized_annual_amount,
    parse_annual_named_colon_amount_list,
)
from .ocr.damaged import (
    parse_ocr_contract_amount_list,
    parse_ocr_broken_numbered_salary_table,
    parse_forma_name_amount_ocr,
    parse_lekarz_inline_anon_list,
)

__all__ = [
    "page_context_contract",
    "parse_indexed_three_col_continuation",
    "parse_indexed_single_salary_markdown",
    "parse_indexed_total_gross_continuation",
    "parse_salary_bracket_index_table",
    "parse_parallel_index_amount_columns",
    "parse_vertical_idx_code_gross_net",
    "parse_vertical_label_amount_pairs",
    "parse_vertical_indexname_amount",
    "parse_vertical_index_code_label_amount",
    "parse_vertical_named_salary_table",
    "parse_vertical_role_named_amount",
    "parse_two_section_vertical_salary",
    "parse_numbered_amount_only_series",
    "parse_vertical_index_amount_series",
    "parse_parallel_name_amount_lists",
    "parse_parallel_doctor_amount_lists",
    "parse_anonymous_amount_only_series",
    "parse_numbered_named_inline_salary",
    "parse_lekarz_inline_salary",
    "parse_embedded_numbered_salary_list",
    "parse_specialty_amount_lines",
    "parse_explicit_annual_prose_salary",
    "parse_body_lekarz_number_amount",
    "parse_body_lp_amount",
    "parse_annual_amount_contract_lines",
    "parse_contract_practice_cost_list",
    "parse_single_anonymized_annual_amount",
    "parse_annual_named_colon_amount_list",
    "parse_ocr_contract_amount_list",
    "parse_ocr_broken_numbered_salary_table",
    "parse_forma_name_amount_ocr",
    "parse_lekarz_inline_anon_list",
]
