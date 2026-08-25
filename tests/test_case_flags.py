"""Procedural correspondence classification tests."""
from fedrowanie_parser.processing.case_flags import classify_case_flags


def test_more_time_and_anonymization_can_coexist():
    text = """
    Informujemy o przedłużeniu terminu udzielenia odpowiedzi.
    Prosimy również o potwierdzenie, czy dane mogą zostać zanonimizowane.
    """
    flags = classify_case_flags(text)

    assert flags.requested_more_time
    assert flags.asked_about_anonymization


def test_processed_information_request():
    text = """
    Wniosek dotyczy informacji przetworzonej. Prosimy o wykazanie
    szczególnego interesu publicznego uzasadniającego jej udostępnienie.
    """
    flags = classify_case_flags(text)

    assert flags.requested_processed_info_justification


def test_fee_and_formal_deficiency_are_independent():
    text = """
    Wzywamy do uzupełnienia wniosku o podpis.
    Jednocześnie informujemy, że udostępnienie może wiązać się z dodatkową opłatą.
    """
    flags = classify_case_flags(text)

    assert flags.formal_deficiency_request
    assert flags.fee_notice
