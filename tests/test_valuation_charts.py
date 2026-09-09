from decimal import Decimal
from pathlib import Path

from matplotlib.figure import Figure

from nike_financial_analysis.charts import (
    VALUATION_SOURCE_NOTE,
    scenario_valuation_chart,
)
from nike_financial_analysis.valuation import build_summary_rows, build_valuation_model


ROOT = Path(__file__).resolve().parents[1]


def test_scenario_valuation_chart_shows_three_values_and_dated_reference():
    rows = build_summary_rows(build_valuation_model(ROOT))
    figure = scenario_valuation_chart(rows)
    assert isinstance(figure, Figure)
    assert len(figure.axes) == 1
    axis = figure.axes[0]
    assert axis.get_ylabel() == "USD per diluted-proxy share"
    assert [tick.get_text() for tick in axis.get_xticklabels()] == ["Bear", "Base", "Bull"]
    assert len(axis.patches) == 3
    assert [Decimal(str(patch.get_height())).quantize(Decimal("0.01")) for patch in axis.patches] == [
        Decimal("30.06"),
        Decimal("47.81"),
        Decimal("59.55"),
    ]
    figure_text = " ".join(text.get_text() for text in figure.texts)
    assert VALUATION_SOURCE_NOTE in figure_text
    assert "September 4, 2026 valuation date" in figure_text
    assert "September 4, 2026 reference price" in axis.get_legend().get_texts()[0].get_text()
