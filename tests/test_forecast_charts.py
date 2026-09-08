from pathlib import Path

from matplotlib.figure import Figure

from nike_financial_analysis.charts import (
    FORECAST_SOURCE_NOTE,
    forecast_fcff_chart,
    forecast_operating_margin_chart,
    forecast_reinvestment_chart,
    forecast_revenue_chart,
)
from nike_financial_analysis.forecast import build_forecast_model, build_long_rows


ROOT = Path(__file__).resolve().parents[1]


def rows():
    return build_long_rows(build_forecast_model(ROOT))


def assert_common_chart_contract(figure: Figure, expected_axes: int) -> None:
    assert isinstance(figure, Figure)
    assert len(figure.axes) == expected_axes
    figure_text = " ".join(text.get_text() for text in figure.texts)
    assert FORECAST_SOURCE_NOTE in figure_text
    assert "owner-approved" not in figure_text.lower()


def assert_historical_anchor_is_visible(axis, historical_label: str) -> None:
    historical = next(line for line in axis.lines if line.get_label() == historical_label)
    scenarios = [
        line for line in axis.lines if line.get_label() in {"Base scenario", "Bull scenario", "Bear scenario"}
    ]
    assert len(scenarios) == 3
    assert historical.get_zorder() > max(line.get_zorder() for line in scenarios)
    for line in scenarios:
        assert tuple(line.get_xdata()) == (4, 5, 6, 7, 8, 9)
        assert line.get_ydata()[0] == historical.get_ydata()[-1]
        assert 0 not in line.get_markevery()


def test_revenue_chart_contains_actual_and_three_scenarios():
    figure = forecast_revenue_chart(rows())
    assert_common_chart_contract(figure, 1)
    axis = figure.axes[0]
    assert axis.get_ylabel() == "USD millions"
    assert len(axis.lines) >= 5
    assert "FY2026" in {tick.get_text() for tick in axis.get_xticklabels()}
    assert "FY2031" in {tick.get_text() for tick in axis.get_xticklabels()}
    assert axis.get_ylim() == (40000.0, 57000.0)
    assert_historical_anchor_is_visible(axis, "Historical revenue")


def test_margin_chart_discloses_derived_measure():
    figure = forecast_operating_margin_chart(rows())
    assert_common_chart_contract(figure, 1)
    assert figure.axes[0].get_ylabel() == "Derived operating margin (%)"
    assert "not Nike-reported consolidated EBIT" in " ".join(
        text.get_text() for text in figure.texts
    )
    assert figure.axes[0].get_ylim()[0] == 0
    assert_historical_anchor_is_visible(
        figure.axes[0], "Historical derived operating margin"
    )


def test_fcff_chart_has_zero_line_and_formula_note():
    figure = forecast_fcff_chart(rows())
    assert_common_chart_contract(figure, 1)
    assert figure.axes[0].get_ylabel() == "USD millions"
    assert "FCFF = NOPAT" in " ".join(text.get_text() for text in figure.texts)
    assert figure.axes[0].get_ylim()[0] == 0
    assert_historical_anchor_is_visible(figure.axes[0], "Historical project FCFF")


def test_reinvestment_chart_uses_three_separate_panels():
    figure = forecast_reinvestment_chart(rows())
    assert_common_chart_contract(figure, 3)
    assert [axis.get_ylabel() for axis in figure.axes] == [
        "D&A / revenue (%)",
        "Capital expenditures / revenue (%)",
        "Operating NWC / revenue (%)",
    ]
    assert [axis.get_ylim() for axis in figure.axes] == [
        (1.2, 1.9),
        (0.8, 2.0),
        (8.5, 12.5),
    ]
    for axis in figure.axes:
        assert_historical_anchor_is_visible(axis, "Historical ratios")
