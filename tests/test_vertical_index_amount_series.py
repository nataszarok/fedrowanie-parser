from fedrowanie_parser.parsing.sequences.vertical import parse_vertical_index_amount_series


def test_chojnice_vertical_lp_annual_amounts():
    text = """Lp.
Łączne wynagrodzenie w roku 2025:
1
345467,71
2
391602,88
3
23530,55
4
172846,12
5
272299,89
6
217739,64
"""
    rows = parse_vertical_index_amount_series(1, 2, "Chojnice", 1, text)

    assert len(rows) == 6
    assert [row.gross_compensation for row in rows] == [
        345467.71, 391602.88, 23530.55,
        172846.12, 272299.89, 217739.64,
    ]


def test_lublin_vertical_lp_annual_amounts_with_currency():
    text = """ŁĄCZNE WYNAGRODZENIE LEKARZY WYPŁACONE W 2025 ROKU,
NIEZALEŻNIE OD POSZCZEGÓLNYCH FORM WYKONYWANIA
OBOWIĄZKÓW
1
78 742,80 zł
2
285 966,80 zł
3
414 954,78 zł
"""
    rows = parse_vertical_index_amount_series(1, 2, "Lublin", 1, text)

    assert len(rows) == 3
    assert [row.gross_compensation for row in rows] == [
        78742.80, 285966.80, 414954.78,
    ]


def test_long_vertical_series_keeps_all_222_rows():
    body = "\n".join(
        item
        for i in range(1, 223)
        for item in (str(i), f"{100000 + i},00")
    )
    text = "Lp.\nŁączne wynagrodzenie w roku 2025:\n" + body

    rows = parse_vertical_index_amount_series(1, 2, "Chojnice", 1, text)

    assert len(rows) == 222
    assert rows[0].source_name == "Lekarz 1"
    assert rows[-1].source_name == "Lekarz 222"


def test_partial_series_does_not_take_over_document():
    text = """Wniosek zawiera informację o łącznym wynagrodzeniu wypłaconym w roku 2025.
13
215 824,28
14
220 000,00
15
230 000,00
"""
    rows = parse_vertical_index_amount_series(1, 2, "Example", 0, text)
    assert rows == []
