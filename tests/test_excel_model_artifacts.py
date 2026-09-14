import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import openpyxl
import pytest

from nike_financial_analysis import excel_model
from nike_financial_analysis.excel_model import (
    WORKBOOK_PATH,
    build_workbook,
    inspect_workbook,
    normalize_workbook_package,
    semantic_digest,
    verify_all_protected_artifacts,
)
from nike_financial_analysis.valuation import build_valuation_model


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_CHECK_IDS = {
    "terminal_bridge_revenue",
    "terminal_bridge_fcff",
    "terminal_value_formula",
    "enterprise_value_equation",
    "equity_value_equation",
    "basic_share_crosscheck",
}


def _number(workbook: openpyxl.Workbook, sheet: str, cell: str) -> Decimal:
    return Decimal(str(workbook[sheet][cell].value))


def _select_scenario(path: Path, scenario: str) -> None:
    workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
    try:
        workbook["Cover"]["D6"] = scenario
        workbook.calculation.calcMode = "auto"
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True
        workbook.save(path)
    finally:
        workbook.close()


def _check_rows(workbook: openpyxl.Workbook) -> dict[str, int]:
    checks = workbook["Checks"]
    return {
        checks[f"A{row}"].value: row
        for row in range(9, checks.max_row + 1)
    }


def _independent_base_sensitivity_value(
    wacc: Decimal, terminal_growth: Decimal
) -> Decimal:
    with (ROOT / "outputs/model_exports/valuation_cash_flows.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["scenario"] == "base"
        ]
    with (ROOT / "config/valuation_assumptions.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        assumptions = {
            row["input_name"]: row["value"] for row in csv.DictReader(handle)
        }

    model_date = date.fromisoformat(assumptions["model_date"])
    explicit_rows = [row for row in rows if row["period_class"] == "explicit_forecast"]
    explicit_pv = sum(
        (
            Decimal(row["fcff"])
            / (Decimal("1") + wacc)
            ** (
                Decimal((date.fromisoformat(row["cash_flow_date"]) - model_date).days)
                / Decimal("365")
            )
            for row in explicit_rows
        ),
        Decimal("0"),
    )
    fy2031 = next(row for row in explicit_rows if row["fiscal_year"] == "FY2031")
    revenue = Decimal(fy2031["revenue"]) * (Decimal("1") + terminal_growth)
    derived = revenue * (
        Decimal(fy2031["gross_margin"])
        - Decimal(fy2031["sga_percent_revenue"])
    )
    tax = max(derived, Decimal("0")) * Decimal(
        fy2031["normalized_tax_rate"]
    )
    nopat = derived - tax
    depreciation = revenue * Decimal(fy2031["da_percent_revenue"])
    capex = revenue * Decimal(fy2031["capex_percent_revenue"])
    operating_nwc = revenue * Decimal(fy2031["operating_nwc_percent_revenue"])
    change_in_operating_nwc = operating_nwc - Decimal(
        fy2031["operating_nwc_proxy"]
    )
    terminal_fcff = nopat + depreciation - capex - change_in_operating_nwc
    terminal_value = terminal_fcff / (wacc - terminal_growth)
    terminal_exponent = Decimal((date(2031, 5, 31) - model_date).days) / Decimal(
        "365"
    )
    pv_terminal = terminal_value / (
        Decimal("1") + wacc
    ) ** terminal_exponent
    equity_bridge = (
        Decimal(assumptions["cash_and_cash_equivalents"])
        + Decimal(assumptions["short_term_investments"])
        - Decimal(assumptions["carrying_interest_bearing_debt"])
        - Decimal(assumptions["redeemable_preferred_stock"])
    )
    diluted_proxy_shares = (
        Decimal(assumptions["class_a_shares_outstanding"])
        + Decimal(assumptions["class_b_shares_outstanding"])
        + Decimal(assumptions["incremental_dilutive_share_proxy"])
    )
    return (explicit_pv + pv_terminal + equity_bridge) / diluted_proxy_shares


def test_published_workbook_has_usable_excel_caches_and_reconciles_to_python():
    path = ROOT / WORKBOOK_PATH
    summary = inspect_workbook(path, ROOT, require_recalculated=True)
    model = build_valuation_model(ROOT)
    cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
    try:
        assert summary["check_status"] == "PASS WITH WARNINGS"
        assert summary["fail_count"] == 0
        assert summary["warning_count"] == 3
        assert _number(cached, "Checks", "D9") == Decimal("2")
        assert abs(_number(cached, "WACC", "E36") - model.wacc_primary.wacc) <= Decimal("1E-9")
        expected = {
            result.scenario: result.value_per_share
            for result in model.scenario_valuations
        }
        for scenario, cell in {"bear": "L26", "base": "M26", "bull": "N26"}.items():
            assert abs(_number(cached, "DCF", cell) - expected[scenario]) <= Decimal("0.01")
        assert abs(_number(cached, "DCF", "E69")) <= Decimal("0.1")
        assert abs(_number(cached, "Sensitivity", "F11") - expected["base"]) <= Decimal("0.01")
    finally:
        cached.close()


def test_same_published_workbook_has_stable_semantic_digest_and_protected_inputs():
    path = ROOT / WORKBOOK_PATH
    first = semantic_digest(path)
    second = semantic_digest(path)
    assert first == second
    assert len(first) == 64
    assert verify_all_protected_artifacts(ROOT)


def test_published_sensitivity_grid_reconciles_to_independent_coordinates():
    path = ROOT / WORKBOOK_PATH
    workbook = openpyxl.load_workbook(path, data_only=True, keep_links=True)
    try:
        maximum_difference = Decimal("0")
        for row in range(9, 14):
            wacc = _number(workbook, "Sensitivity", f"C{row}")
            for column in "DEFGH":
                growth = _number(workbook, "Sensitivity", f"{column}8")
                actual = _number(workbook, "Sensitivity", f"{column}{row}")
                expected = _independent_base_sensitivity_value(wacc, growth)
                maximum_difference = max(
                    maximum_difference, abs(actual - expected)
                )
        assert maximum_difference <= Decimal("1E-9")
    finally:
        workbook.close()


def test_sensitivity_mutation_diagnostics_are_independently_derived():
    model = build_valuation_model(ROOT)
    wacc = model.wacc_primary.wacc
    headline_at_three_percent = _independent_base_sensitivity_value(
        wacc, Decimal("0.030")
    )
    first_column_at_two_percent = _independent_base_sensitivity_value(
        wacc, Decimal("0.020")
    )
    assert abs(
        headline_at_three_percent - Decimal("51.14814974866544370993658586")
    ) <= Decimal("1E-24")
    assert abs(
        first_column_at_two_percent - Decimal("44.98042563536837417451980635")
    ) <= Decimal("1E-24")


@pytest.mark.excel_integration
def test_every_scenario_passes_after_desktop_excel_recalculation():
    model = build_valuation_model(ROOT)
    expected_values = {
        result.scenario.title(): result.value_per_share
        for result in model.scenario_valuations
    }

    with TemporaryDirectory(prefix="nike-excel-model-") as temp_dir:
        path = Path(temp_dir) / "nike_valuation_model.candidate.xlsx"
        build_workbook(ROOT, path)
        for scenario in ("Base", "Bear", "Bull", "Base"):
            _select_scenario(path, scenario)
            excel_model._run_excel_recalculation(ROOT, path)
            normalize_workbook_package(path)
            summary = inspect_workbook(
                path,
                ROOT,
                require_recalculated=True,
                expected_scenario=scenario,
            )
            formulas = openpyxl.load_workbook(
                path, data_only=False, keep_links=True
            )
            cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
            try:
                rows = _check_rows(formulas)
                assert cached["Cover"]["D6"].value == scenario
                assert cached["Cover"]["D28"].value == "PASS WITH WARNINGS"
                assert cached["Checks"]["H6"].value == "PASS WITH WARNINGS"
                assert cached["Checks"]["A6"].value == "PASS"
                assert cached["Checks"]["C6"].value == "MATCHES APPROVED"
                assert cached["Checks"]["E6"].value == "WARNINGS PRESENT"
                assert cached["Checks"]["G6"].value == "PASS"
                assert summary["warning_count"] == 3
                assert summary["fail_count"] == 0
                assert Decimal(summary["xnpv_difference"]) == Decimal("0")
                assert abs(
                    _number(cached, "Cover", "D24") - expected_values[scenario]
                ) <= Decimal("0.01")
                assert all(
                    cached["Checks"][f"H{rows[check_id]}"].value == "PASS"
                    for check_id in SCENARIO_CHECK_IDS
                )
            finally:
                formulas.close()
                cached.close()


@pytest.mark.excel_integration
def test_scenario_expected_value_change_causes_selected_check_failure():
    with TemporaryDirectory(prefix="nike-excel-model-") as temp_dir:
        path = Path(temp_dir) / "nike_valuation_model.candidate.xlsx"
        build_workbook(ROOT, path)
        _select_scenario(path, "Bear")
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            formula = str(workbook["DCF"]["L10"].value)
            workbook["DCF"]["L10"] = f"={formula.removeprefix('=')}+100"
            workbook.save(path)
        finally:
            workbook.close()

        excel_model._run_excel_recalculation(ROOT, path)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        formulas = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            row = _check_rows(formulas)["terminal_bridge_revenue"]
            assert cached["Checks"][f"H{row}"].value == "FAIL"
            assert cached["Checks"]["A6"].value == "FAIL"
            assert cached["Checks"]["H6"].value == "FAIL"
            assert cached["Cover"]["D28"].value == "FAIL"
        finally:
            cached.close()
            formulas.close()


@pytest.mark.excel_integration
def test_sensitivity_mutations_and_snapshot_departure_are_classified():
    model = build_valuation_model(ROOT)
    base_value = next(
        result.value_per_share
        for result in model.scenario_valuations
        if result.scenario == "base"
    )

    def assert_sensitivity_calculations_pass(
        cached: openpyxl.Workbook, rows: dict[str, int]
    ) -> None:
        for row in range(9, 14):
            for column in "DEFGH":
                assert (
                    cached["Checks"][
                        f"H{rows[f'sensitivity_calculation_{column}{row}']}"
                    ].value
                    == "PASS"
                )

    with TemporaryDirectory(prefix="nike-excel-model-") as temp_dir:
        path = Path(temp_dir) / "nike_valuation_model.candidate.xlsx"

        build_workbook(ROOT, path)
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            workbook["Sources"]["D30"] = 0.03
            workbook.save(path)
        finally:
            workbook.close()
        excel_model._run_excel_recalculation(ROOT, path)
        formulas = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        try:
            rows = _check_rows(formulas)
            assert abs(
                _number(cached, "DCF", "M26")
                - Decimal("51.14814974866544370993658586")
            ) <= Decimal("1E-9")
            assert abs(_number(cached, "Sensitivity", "F11") - base_value) <= Decimal(
                "0.01"
            )
            assert (
                cached["Checks"][f"H{rows['sensitivity_center']}"].value
                == "NOT APPLICABLE — COORDINATES DIFFER"
            )
            assert cached["Checks"]["A6"].value == "PASS"
            assert cached["Checks"]["C6"].value == "DIFFERS FROM APPROVED"
            assert cached["Checks"]["G6"].value == "PASS"
            assert_sensitivity_calculations_pass(cached, rows)
            assert (
                cached["Checks"]["H6"].value
                == "NOT PUBLISHABLE — DIFFERS FROM APPROVED"
            )
        finally:
            formulas.close()
            cached.close()

        build_workbook(ROOT, path)
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            workbook["Sources"]["D36"] = 0.02
            workbook.save(path)
        finally:
            workbook.close()
        excel_model._run_excel_recalculation(ROOT, path)
        formulas = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        try:
            rows = _check_rows(formulas)
            assert _number(cached, "Sensitivity", "D8") == Decimal("0.02")
            assert _number(cached, "Sensitivity", "D18") == Decimal("0.02")
            assert abs(
                _number(cached, "Sensitivity", "D11")
                - Decimal("44.98042563536837417451980635")
            ) <= Decimal("1E-9")
            assert abs(
                _number(cached, "Sensitivity", "D11")
                - _number(cached, "Sensitivity", "E11")
            ) <= Decimal("1E-9")
            assert (
                cached["Checks"][
                    f"H{rows['sensitivity_growth_coordinate_order']}"
                ].value
                == "INPUT WARNING"
            )
            for row in range(9, 14):
                assert (
                    cached["Checks"][
                        f"H{rows[f'sensitivity_growth_monotonicity_{row}']}"
                    ].value
                    == "NOT APPLICABLE — DUPLICATE OR UNORDERED COORDINATES"
                )
            assert cached["Checks"]["A6"].value == "PASS"
            assert cached["Checks"]["C6"].value == "DIFFERS FROM APPROVED"
            assert cached["Checks"]["G6"].value == "PASS"
            assert_sensitivity_calculations_pass(cached, rows)
            assert (
                cached["Checks"]["H6"].value
                == "NOT PUBLISHABLE — DIFFERS FROM APPROVED"
            )
        finally:
            formulas.close()
            cached.close()

        build_workbook(ROOT, path)
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            workbook["Sources"]["D19"] = 0.05
            workbook.save(path)
        finally:
            workbook.close()
        excel_model._run_excel_recalculation(ROOT, path)
        formulas = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        try:
            rows = _check_rows(formulas)
            assert cached["Checks"]["A6"].value == "PASS"
            assert cached["Checks"]["C6"].value == "DIFFERS FROM APPROVED"
            assert cached["Checks"]["E6"].value == "WARNINGS PRESENT"
            assert cached["Checks"]["G6"].value == "PASS"
            assert_sensitivity_calculations_pass(cached, rows)
            assert (
                cached["Checks"]["H6"].value
                == "NOT PUBLISHABLE — DIFFERS FROM APPROVED"
            )
        finally:
            formulas.close()
            cached.close()

        with pytest.raises(
            ValueError, match="embedded inputs differ from the approved"
        ):
            inspect_workbook(path, ROOT, require_recalculated=True)

        build_workbook(ROOT, path)
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            workbook["Sensitivity"]["F11"] = "=1"
            workbook.save(path)
        finally:
            workbook.close()
        excel_model._run_excel_recalculation(ROOT, path)
        formulas = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        try:
            rows = _check_rows(formulas)
            assert (
                cached["Checks"][
                    f"H{rows['sensitivity_calculation_F11']}"
                ].value
                == "FAIL"
            )
            assert cached["Checks"]["A6"].value == "FAIL"
            assert cached["Checks"]["H6"].value == "FAIL"
            assert cached["Cover"]["D28"].value == "FAIL"
        finally:
            formulas.close()
            cached.close()

        build_workbook(ROOT, path)
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            workbook["Sensitivity"]["F11"] = "=47.806760260823"
            workbook.save(path)
        finally:
            workbook.close()
        excel_model._run_excel_recalculation(ROOT, path)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        try:
            assert abs(
                _number(cached, "Sensitivity", "F11") - base_value
            ) <= Decimal("0.01")
            assert cached["Checks"]["A6"].value == "PASS"
            assert cached["Checks"]["C6"].value == "MATCHES APPROVED"
            assert cached["Checks"]["H6"].value == "PASS WITH WARNINGS"
        finally:
            cached.close()
        with pytest.raises(
            ValueError,
            match="Sensitivity formula-integrity mismatch at Sensitivity!F11",
        ):
            inspect_workbook(path, ROOT, require_recalculated=True)

        build_workbook(ROOT, path)
        workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        try:
            workbook["Sources"]["G7"] = "VS01VS02"
            workbook.save(path)
        finally:
            workbook.close()
        excel_model._run_excel_recalculation(ROOT, path)
        formulas = openpyxl.load_workbook(path, data_only=False, keep_links=True)
        cached = openpyxl.load_workbook(path, data_only=True, keep_links=True)
        try:
            rows = _check_rows(formulas)
            assert (
                cached["Checks"][
                    f"H{rows['valuation_source_id_resolution']}"
                ].value
                == "FAIL"
            )
            assert cached["Checks"]["G6"].value == "FAIL"
            assert cached["Checks"]["H6"].value == "FAIL"
            assert cached["Cover"]["D28"].value == "FAIL"
        finally:
            formulas.close()
            cached.close()
