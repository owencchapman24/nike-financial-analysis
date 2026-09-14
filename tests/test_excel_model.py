from pathlib import Path

import openpyxl
import pytest

from nike_financial_analysis import excel_model
from nike_financial_analysis.excel_model import (
    REQUIRED_DEFINED_NAMES,
    SHEET_ORDER,
    build_workbook,
    inspect_workbook,
    normalize_workbook_package,
)


ROOT = Path(__file__).resolve().parents[1]


def test_formula_workbook_has_approved_structure_and_native_logic(tmp_path):
    path = tmp_path / "candidate.xlsx"
    build_workbook(ROOT, path)
    normalize_workbook_package(path)

    summary = inspect_workbook(path, ROOT, require_recalculated=False)
    workbook = openpyxl.load_workbook(path, data_only=False, keep_links=True)
    try:
        assert tuple(workbook.sheetnames) == SHEET_ORDER
        assert all(workbook[name].sheet_state == "visible" for name in SHEET_ORDER)
        assert REQUIRED_DEFINED_NAMES <= set(workbook.defined_names)
        assert workbook["Cover"]["D6"].value == "Base"
        validation = workbook["Cover"].data_validations.dataValidation[0]
        assert validation.formula1 == "ScenarioList"
        assert "D6" in str(validation.sqref)
        assert workbook["WACC"]["E36"].data_type == "f"
        assert workbook["DCF"]["E59"].data_type == "f"
        assert workbook["Sensitivity"]["F11"].data_type == "f"
        checks = workbook["Checks"]
        check_rows = {
            checks[f"A{row}"].value: row
            for row in range(9, checks.max_row + 1)
        }
        scenario_expected_rows = {
            "terminal_bridge_revenue": 10,
            "terminal_bridge_fcff": 20,
            "terminal_value_formula": 22,
            "enterprise_value_equation": 24,
            "equity_value_equation": 25,
            "basic_share_crosscheck": 27,
        }
        for check_id, dcf_row in scenario_expected_rows.items():
            row = check_rows[check_id]
            assert checks[f"C{row}"].value == "selected scenario"
            assert checks[f"E{row}"].value == (
                "=CHOOSE(MATCH(SelectedScenario,ScenarioList,0),"
                f"'DCF'!L{dcf_row},'DCF'!M{dcf_row},'DCF'!N{dcf_row})"
            )
        selected_block = range(
            check_rows["discount_exponent_FY2027"],
            check_rows["basic_share_crosscheck"] + 1,
        )
        assert all(checks[f"C{row}"].value != "selected Base" for row in selected_block)
        formulas = [
            str(cell.value)
            for sheet in workbook.worksheets
            for row in sheet.iter_rows()
            for cell in row
            if cell.data_type == "f"
        ]
        assert summary["formula_count"] >= 1_000
        assert any("XNPV(" in formula.upper() for formula in formulas)
        assert not any("INDIRECT(" in formula.upper() for formula in formulas)
        assert not any("OFFSET(" in formula.upper() for formula in formulas)
    finally:
        workbook.close()


def test_pre_excel_recalculation_sentinel_is_deliberately_invalid(tmp_path):
    path = tmp_path / "candidate.xlsx"
    build_workbook(ROOT, path)
    cached = openpyxl.load_workbook(path, data_only=True)
    try:
        assert cached["Checks"]["D9"].value == -999
        assert cached["Cover"]["D8"].value.date().isoformat() == "2026-09-04"
        assert cached["Sources"]["N13"].value.date().isoformat() == "2026-09-04"
        assert cached["DCF"]["D12"].value.date().isoformat() == "2026-09-04"
    finally:
        cached.close()


def test_fail_closed_build_does_not_publish_unverified_workbook(tmp_path, monkeypatch):
    destination = tmp_path / "model" / "nike_valuation_model.xlsx"

    def fail_recalculation(*_args, **_kwargs):
        raise RuntimeError("controlled recalculation failure")

    monkeypatch.setattr(excel_model, "_run_excel_recalculation", fail_recalculation)
    with pytest.raises(RuntimeError, match="controlled recalculation failure"):
        excel_model.build_verified_workbook(ROOT, destination)
    assert not destination.exists()
    assert not destination.with_suffix(".publishing.xlsx").exists()


def test_recalculation_script_is_bounded_and_never_terminates_excel_globally():
    script = (ROOT / "scripts/recalculate_workbook.ps1").read_text(encoding="utf-8")
    assert "CalculateFullRebuild" in script
    assert "TimeoutSeconds" in script
    assert "DedicatedProcessId=" in script
    assert "DisplayAlerts = $false" in script
    assert "EnableEvents = $false" in script
    assert "AskToUpdateLinks = $false" in script
    assert "CircularReference" in script
    assert "Stop-Process" not in script
    assert "taskkill" not in script.lower()
