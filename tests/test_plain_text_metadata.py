"""Regression tests for technical document metadata in plain-text parsing."""
from fedrowanie_parser.parsing.plain_text import parse_plain_lines


def test_documentemail_metadata_is_not_salary():
    page = """
93
Clean
DocumentEmail
false
21
false
false
false
PL
X-NONE
X-NONE
"""
    rows = parse_plain_lines(124467, 4556, "Test hospital", 1, page)
    assert rows == []
