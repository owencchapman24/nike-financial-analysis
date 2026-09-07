"""Static, publication-ready charts for the historical analysis."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure


COLORS = {
    "navy": "#264653",
    "blue": "#0072B2",
    "sky": "#56B4E9",
    "green": "#009E73",
    "orange": "#E69F00",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#6B7280",
    "light_gray": "#D1D5DB",
    "ink": "#1F2937",
}
FISCAL_YEARS = ("FY2022", "FY2023", "FY2024", "FY2025", "FY2026")
SOURCE_NOTE = (
    "Source: Nike 10-K filings via SEC Company Facts; project calculations. "
    "FY2022-FY2026."
)
CHART_FILENAMES = (
    "01_revenue_and_growth.png",
    "02_margin_trends.png",
    "03_cash_generation.png",
    "04_working_capital_and_liquidity.png",
    "05_capital_structure.png",
)


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.edgecolor": COLORS["light_gray"],
            "axes.labelcolor": COLORS["ink"],
            "xtick.color": COLORS["ink"],
            "ytick.color": COLORS["ink"],
            "text.color": COLORS["ink"],
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _rows_by_metric(
    kpi_rows: list[dict[str, str]], metric: str
) -> list[dict[str, str]]:
    rows = [row for row in kpi_rows if row["metric"] == metric]
    rows.sort(key=lambda row: FISCAL_YEARS.index(row["fiscal_year"]))
    if tuple(row["fiscal_year"] for row in rows) != FISCAL_YEARS:
        raise ValueError(f"Chart metric {metric} does not contain all five fiscal years.")
    return rows


def _decimal_series(
    kpi_rows: list[dict[str, str]], metric: str
) -> list[Decimal | None]:
    return [
        Decimal(row["value"]) if row["value"] != "" else None
        for row in _rows_by_metric(kpi_rows, metric)
    ]


def _float_series(
    kpi_rows: list[dict[str, str]], metric: str, *, scale: Decimal = Decimal("1")
) -> list[float]:
    """Convert Decimal values only at the Matplotlib rendering boundary."""

    return [
        float(value * scale) if value is not None else float("nan")
        for value in _decimal_series(kpi_rows, metric)
    ]


def _value(
    kpi_rows: list[dict[str, str]], metric: str, fiscal_year: str = "FY2026"
) -> Decimal:
    row = next(
        item
        for item in _rows_by_metric(kpi_rows, metric)
        if item["fiscal_year"] == fiscal_year
    )
    if row["value"] == "":
        raise ValueError(f"Chart annotation {metric} in {fiscal_year} has no value.")
    return Decimal(row["value"])


def _finish_figure(fig: Figure) -> Figure:
    fig.text(0.01, 0.015, SOURCE_NOTE, fontsize=8, color=COLORS["gray"])
    return fig


def _grid(axis: Axes) -> None:
    axis.grid(axis="y", color="#E5E7EB", linewidth=0.8)
    axis.set_axisbelow(True)


def revenue_and_growth_chart(kpi_rows: list[dict[str, str]]) -> Figure:
    """Plot revenue and annual growth in separate panels."""

    _apply_style()
    revenue = _float_series(kpi_rows, "revenue")
    growth = _float_series(kpi_rows, "revenue_growth", scale=Decimal("100"))
    positions = list(range(len(FISCAL_YEARS)))
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(12, 7), dpi=150, gridspec_kw={"height_ratios": [2, 1]}
    )
    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.12, hspace=0.35)
    fig.suptitle("Revenue and annual growth", fontsize=16, fontweight="bold")

    bars = top.bar(positions, revenue, color=COLORS["blue"], width=0.62)
    top.set_ylabel("USD millions")
    top.set_xticks(positions, FISCAL_YEARS)
    top.set_ylim(0, max(revenue) * 1.12)
    _grid(top)
    for bar, value in zip(bars, revenue, strict=True):
        top.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(revenue) * 0.018,
            f"${value:,.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    peak = _value(kpi_rows, "peak_revenue")
    cagr = _value(kpi_rows, "revenue_cagr_five_observations")
    peak_year = FISCAL_YEARS[revenue.index(max(revenue))]
    peak_to_fy2026 = (
        (peak - _value(kpi_rows, "revenue", "FY2026")) / peak * Decimal("100")
    )
    fig.text(
        0.09,
        0.89,
        f"Peak: {peak_year} USD {peak:,.0f}m | FY2024-FY2026: −{peak_to_fy2026:.1f}% | FY2022-FY2026 CAGR: {cagr * 100:.1f}%",
        fontsize=9,
        color=COLORS["gray"],
    )

    growth_colors = [
        COLORS["blue"] if value >= 0 else COLORS["vermillion"] for value in growth
    ]
    growth_bars = bottom.bar(positions, growth, color=growth_colors, width=0.62)
    bottom.axhline(0, color=COLORS["ink"], linewidth=0.9)
    bottom.set_ylabel("YoY growth (%)")
    bottom.set_xticks(positions, FISCAL_YEARS)
    _grid(bottom)
    for index, (bar, value) in enumerate(zip(growth_bars, growth, strict=True)):
        if index == 0:
            continue
        if value < 0:
            bottom.text(
                bar.get_x() + bar.get_width() / 2,
                value / 2,
                f"{value:.1f}%",
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="white",
            )
        else:
            bottom.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.45,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    bottom.text(
        positions[0],
        0.5,
        "N/A",
        ha="center",
        va="bottom",
        fontsize=9,
        color=COLORS["gray"],
    )
    return _finish_figure(fig)


def margin_trends_chart(kpi_rows: list[dict[str, str]]) -> Figure:
    """Plot gross, derived operating, and net margins."""

    _apply_style()
    fig, axis = plt.subplots(figsize=(12, 7), dpi=150)
    fig.subplots_adjust(left=0.09, right=0.87, top=0.88, bottom=0.14)
    axis.set_title("Profitability margins")
    series = (
        ("gross_margin", "Gross margin", COLORS["blue"], "-"),
        ("operating_margin", "Derived operating margin", COLORS["orange"], "--"),
        ("net_margin", "Net margin", COLORS["green"], "-"),
    )
    for metric, label, color, line_style in series:
        values = _float_series(kpi_rows, metric, scale=Decimal("100"))
        axis.plot(
            FISCAL_YEARS,
            values,
            marker="o",
            linewidth=2.4,
            linestyle=line_style,
            color=color,
            label=label,
        )
        axis.text(
            4.08,
            values[-1],
            f"{values[-1]:.1f}%",
            color=color,
            va="center",
            fontsize=9,
        )
    axis.set_ylabel("Margin (%)")
    axis.set_ylim(bottom=0)
    axis.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0),
        ncols=3,
    )
    _grid(axis)
    fig.text(
        0.01,
        0.045,
        "Derived operating margin uses gross profit less total SG&A. Nike does not report this consolidated subtotal; it is not segment EBIT.",
        fontsize=8,
        color=COLORS["gray"],
    )
    return _finish_figure(fig)


def cash_generation_chart(kpi_rows: list[dict[str, str]]) -> Figure:
    """Plot cash generation and CFO-to-net-income cash conversion."""

    _apply_style()
    positions = list(range(len(FISCAL_YEARS)))
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(12, 7), dpi=150, gridspec_kw={"height_ratios": [2, 1]}
    )
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.12, hspace=0.35)
    fig.suptitle("Cash generation and conversion", fontsize=16, fontweight="bold")

    width = 0.24
    cash_series = (
        ("operating_cash_flow", "Operating cash flow", COLORS["blue"], -width),
        ("capital_expenditures", "Capital expenditures", COLORS["orange"], 0),
        ("free_cash_flow", "Free cash flow", COLORS["green"], width),
    )
    for metric, label, color, offset in cash_series:
        values = _float_series(kpi_rows, metric)
        top.bar([position + offset for position in positions], values, width, label=label, color=color)
    top.set_ylabel("USD millions")
    top.set_xticks(positions, FISCAL_YEARS)
    top.set_ylim(bottom=0)
    top.legend(frameon=False, ncols=3, loc="upper right")
    top.text(
        0.01,
        0.92,
        "Capital expenditures are shown as a positive investment amount.",
        transform=top.transAxes,
        fontsize=9,
        color=COLORS["gray"],
    )
    _grid(top)

    conversion = _float_series(kpi_rows, "cash_conversion")
    bottom.plot(
        FISCAL_YEARS,
        conversion,
        marker="o",
        linewidth=2.4,
        color=COLORS["purple"],
    )
    bottom.axhline(1.0, color=COLORS["gray"], linestyle="--", linewidth=1.1)
    bottom.text(0.02, 1.02, "1.0x reference", color=COLORS["gray"], fontsize=8)
    bottom.set_ylabel("CFO / net income (x)")
    bottom.set_ylim(bottom=0)
    _grid(bottom)
    for index, value in enumerate(conversion):
        bottom.text(index, value + 0.045, f"{value:.2f}x", ha="center", fontsize=9)
    return _finish_figure(fig)


def working_capital_liquidity_chart(kpi_rows: list[dict[str, str]]) -> Figure:
    """Plot liquidity, current ratio, and working-capital balances."""

    _apply_style()
    positions = list(range(len(FISCAL_YEARS)))
    fig, axes = plt.subplots(
        3, 1, figsize=(12, 8), dpi=150, gridspec_kw={"height_ratios": [1.25, 1, 1.25]}
    )
    fig.subplots_adjust(left=0.09, right=0.97, top=0.92, bottom=0.1, hspace=0.42)
    fig.suptitle("Working capital and liquidity", fontsize=16, fontweight="bold")

    width = 0.34
    liquidity = _float_series(kpi_rows, "cash_and_short_term_investments")
    net_working_capital = _float_series(kpi_rows, "net_working_capital")
    axes[0].bar(
        [position - width / 2 for position in positions],
        liquidity,
        width,
        color=COLORS["blue"],
        label="Cash + short-term investments",
    )
    axes[0].bar(
        [position + width / 2 for position in positions],
        net_working_capital,
        width,
        color=COLORS["green"],
        label="Net working capital",
    )
    axes[0].set_ylabel("USD millions")
    axes[0].set_xticks(positions, FISCAL_YEARS)
    axes[0].legend(frameon=False, ncols=2, loc="upper right")
    axes[0].set_ylim(bottom=0)
    _grid(axes[0])

    current_ratio = _float_series(kpi_rows, "current_ratio")
    axes[1].plot(
        FISCAL_YEARS,
        current_ratio,
        marker="o",
        linewidth=2.4,
        color=COLORS["purple"],
    )
    axes[1].set_ylabel("Current ratio (x)")
    axes[1].set_ylim(bottom=0)
    _grid(axes[1])
    for index, value in enumerate(current_ratio):
        axes[1].text(index, value + 0.08, f"{value:.2f}x", ha="center", fontsize=8)

    for metric, label, color in (
        ("accounts_receivable", "Accounts receivable", COLORS["orange"]),
        ("inventory", "Inventory", COLORS["blue"]),
    ):
        axes[2].plot(
            FISCAL_YEARS,
            _float_series(kpi_rows, metric),
            marker="o",
            linewidth=2.4,
            color=color,
            label=label,
        )
    axes[2].set_ylabel("USD millions")
    axes[2].set_xlabel("Nike fiscal year ended May 31")
    axes[2].set_ylim(bottom=0)
    axes[2].legend(
        frameon=False,
        ncols=2,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.16),
    )
    _grid(axes[2])
    return _finish_figure(fig)


def capital_structure_chart(kpi_rows: list[dict[str, str]]) -> Figure:
    """Plot debt composition, leases, liquidity, and signed net debt."""

    _apply_style()
    positions = list(range(len(FISCAL_YEARS)))
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(12, 7), dpi=150, gridspec_kw={"height_ratios": [1.2, 1]}
    )
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.12, hspace=0.38)
    fig.suptitle("Interest-bearing debt, leases, and liquidity", fontsize=16, fontweight="bold")

    components = (
        ("notes_payable_and_short_term_borrowings", "Notes payable / short-term borrowings", COLORS["orange"]),
        ("current_portion_long_term_debt", "Current portion of long-term debt", COLORS["sky"]),
        ("noncurrent_long_term_debt", "Noncurrent long-term debt", COLORS["navy"]),
    )
    bottoms = [0.0] * len(FISCAL_YEARS)
    for metric, label, color in components:
        values = _float_series(kpi_rows, metric)
        top.bar(positions, values, bottom=bottoms, width=0.62, label=label, color=color)
        bottoms = [base + value for base, value in zip(bottoms, values, strict=True)]
    top.set_ylabel("USD millions")
    top.set_xticks(positions, FISCAL_YEARS)
    top.set_ylim(bottom=0)
    top.legend(frameon=False, ncols=3, loc="upper right", fontsize=8)
    _grid(top)

    for metric, label, color, line_style in (
        ("total_interest_bearing_debt", "Interest-bearing debt", COLORS["navy"], "-"),
        ("total_operating_lease_liabilities", "Operating lease liabilities", COLORS["orange"], "--"),
        ("cash_and_short_term_investments", "Cash + short-term investments", COLORS["green"], "-"),
        ("net_debt_after_cash_and_short_term_investments", "Signed net debt (negative = net cash)", COLORS["purple"], "-"),
    ):
        bottom.plot(
            FISCAL_YEARS,
            _float_series(kpi_rows, metric),
            marker="o",
            linewidth=2.1,
            linestyle=line_style,
            color=color,
            label=label,
        )
    bottom.axhline(0, color=COLORS["ink"], linewidth=0.9)
    bottom.set_ylabel("USD millions")
    bottom.legend(frameon=False, ncols=2, loc="upper right", fontsize=8)
    _grid(bottom)
    signed_net_debt = _value(
        kpi_rows, "net_debt_after_cash_and_short_term_investments"
    )
    endpoint_label = (
        f"FY2026 net cash: ${abs(signed_net_debt):,.0f}m"
        if signed_net_debt < 0
        else f"FY2026 net debt: ${signed_net_debt:,.0f}m"
    )
    fig.text(
        0.09,
        0.47,
        endpoint_label.replace("$", "USD ") + "; operating leases remain separate.",
        fontsize=9,
        color=COLORS["gray"],
    )
    return _finish_figure(fig)


def save_chart(figure: Figure, path: Path) -> None:
    """Save a deterministic PNG without runtime timestamps or local paths."""

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        path,
        dpi=150,
        facecolor="white",
        metadata={"Software": "nike-financial-analysis"},
    )
    plt.close(figure)


def generate_all_charts(
    kpi_rows: list[dict[str, str]], output_dir: Path
) -> tuple[Path, ...]:
    """Generate the complete approved five-chart set."""

    builders: tuple[Callable[[list[dict[str, str]]], Figure], ...] = (
        revenue_and_growth_chart,
        margin_trends_chart,
        cash_generation_chart,
        working_capital_liquidity_chart,
        capital_structure_chart,
    )
    paths: list[Path] = []
    for filename, builder in zip(CHART_FILENAMES, builders, strict=True):
        path = output_dir / filename
        save_chart(builder(kpi_rows), path)
        paths.append(path)
    return tuple(paths)
