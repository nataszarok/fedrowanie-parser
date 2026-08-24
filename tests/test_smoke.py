def test_import_package():
    import fedrowanie_parser

    assert fedrowanie_parser.__version__ == "0.38.0"


def test_import_core_modules():
    from fedrowanie_parser import cli, constants, models, pipeline
    from fedrowanie_parser.io import source_repository, storage
    from fedrowanie_parser.processing import document, normalization
    from fedrowanie_parser.parsing import tables, plain_text, layouts
    from fedrowanie_parser.parsing.structured import continuations
    from fedrowanie_parser.parsing.sequences import vertical, inline
    from fedrowanie_parser.parsing.ocr import damaged
    from fedrowanie_parser.services import case_extraction
    from fedrowanie_parser.enrichment import (
        attachment_contract,
        contract_semantic,
        doctor_initials,
        doctor_status,
        organizational_unit,
        person_name,
        specialization,
        unit_column,
    )
    from fedrowanie_parser.special_cases import (
        monthly_ledger,
        multi_contract_columns,
        section_salary_list,
    )
