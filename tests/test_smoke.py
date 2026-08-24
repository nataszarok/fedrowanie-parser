def test_import_package():
    import fedrowanie_parser
    assert fedrowanie_parser.__version__ == "0.36.0"

def test_import_modules():
    from fedrowanie_parser import (
        cli, common, document, models, pipeline, storage,
        parsers_tables, parsers_layout, parsers_plain,
        attachment_contract_context, contract_semantic_context,
        doctor_initials_context, doctor_status_context,
        monthly_ledger_annualizer_v2_local_fuzzy, multi_contract_columns,
        organizational_unit_context, person_name_context,
        section_salary_list, specialization_context, unit_column_context,
    )
