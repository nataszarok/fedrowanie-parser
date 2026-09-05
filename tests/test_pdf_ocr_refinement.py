from fedrowanie_parser.ingestion.extractors.pdf import _refine_ambiguous_leading_digit


def test_refines_leading_one_to_seven_when_every_other_digit_matches():
    ocr = {"refinement_candidates": [(239.4, 76847.50)]}
    assert _refine_ambiguous_leading_digit(ocr, 239.5, 16847.50) == 76847.50


def test_does_not_change_when_remaining_digits_do_not_match():
    ocr = {"refinement_candidates": [(239.4, 72840.00)]}
    assert _refine_ambiguous_leading_digit(ocr, 239.5, 11840.00) == 11840.00
