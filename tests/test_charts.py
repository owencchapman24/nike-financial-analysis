from pathlib import Path

import matplotlib.image as mpimg

from nike_financial_analysis.analysis import (
    build_analysis,
    build_kpi_rows,
    load_historical_data,
)
from nike_financial_analysis.charts import (
    SOURCE_NOTE,
    capital_structure_chart,
    cash_generation_chart,
    margin_trends_chart,
    revenue_and_growth_chart,
    save_chart,
    working_capital_liquidity_chart,
)


ROOT = Path(__file__).resolve().parents[1]


def kpi_rows():
    analysis = build_analysis(
        load_historical_data(ROOT / "data/processed/nike_financials.csv")
    )
    return build_kpi_rows(analysis)


def test_chart_panel_counts_units_and_source_notes():
    rows = kpi_rows()
    figures = (
        (revenue_and_growth_chart(rows), 2),
        (margin_trends_chart(rows), 1),
        (cash_generation_chart(rows), 2),
        (working_capital_liquidity_chart(rows), 3),
        (capital_structure_chart(rows), 2),
    )

    for figure, expected_axes in figures:
        assert len(figure.axes) == expected_axes
        assert any(text.get_text() == SOURCE_NOTE for text in figure.texts)
        assert any(axis.get_ylabel() for axis in figure.axes)
        figure.clear()


def test_cash_conversion_uses_ratio_axis_and_one_x_reference():
    figure = cash_generation_chart(kpi_rows())
    conversion_axis = figure.axes[1]

    assert conversion_axis.get_ylabel() == "CFO / net income (x)"
    assert any(set(line.get_ydata()) == {1.0} for line in conversion_axis.lines)
    figure.clear()


def test_margin_and_capital_structure_disclosures_are_visible():
    rows = kpi_rows()
    margin = margin_trends_chart(rows)
    capital = capital_structure_chart(rows)

    assert any("not segment EBIT" in text.get_text() for text in margin.texts)
    assert any(
        "negative = net cash" in line.get_label() for line in capital.axes[1].lines
    )
    assert any(
        "operating leases remain separate" in text.get_text()
        for text in capital.texts
    )
    margin.clear()
    capital.clear()


def test_saved_chart_is_nonempty_and_approved_dimensions(tmp_path):
    output = tmp_path / "chart.png"
    save_chart(revenue_and_growth_chart(kpi_rows()), output)

    image = mpimg.imread(output)

    assert output.stat().st_size > 10_000
    assert image.shape[1] == 1800
    assert image.shape[0] == 1050
