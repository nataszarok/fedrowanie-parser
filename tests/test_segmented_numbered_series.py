from fedrowanie_parser.models import SalaryRow
from fedrowanie_parser.pipeline import _reconcile_numbered_annual_series


def _row(idx, amount, parser="plain-vertical"):
    return SalaryRow(
        1, 2, "Hospital", f"Lekarz {idx}", "", "",
        None, amount, 1, parser, "średnia", f"{idx} | {amount}",
    )


def test_reconcile_keeps_earlier_layout_and_replaces_later_segment():
    base = [_row(i, i * 1000) for i in range(1, 13)]
    base += [_row(i, 1) for i in range(13, 18)]
    segment = [_row(i, i * 1000, "vertical-index-amount-series") for i in range(13, 18)]

    rows = _reconcile_numbered_annual_series(base, segment)

    assert len(rows) == 17
    values = {int(r.source_name.split()[-1]): r.gross_compensation for r in rows}
    assert values[12] == 12000
    assert values[13] == 13000
    assert values[17] == 17000


def test_reconcile_drops_year_as_index_false_positive():
    base = [_row(i, i * 1000) for i in range(1, 6)]
    base.append(_row(2025, 1))
    segment = [_row(i, i * 1000, "vertical-index-amount-series") for i in range(2, 6)]

    rows = _reconcile_numbered_annual_series(base, segment)

    assert len(rows) == 5
    assert all(r.source_name != "Lekarz 2025" for r in rows)
