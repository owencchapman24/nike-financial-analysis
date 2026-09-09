from decimal import Decimal
from pathlib import Path

import openpyxl

from nike_financial_analysis.excel_model import (
    WORKBOOK_PATH,
    inspect_workbook,
    semantic_digest,
    verify_all_protected_artifacts,
)
from nike_financial_analysis.valuation import build_valuation_model


ROOT = Path(__file__).resolve().parents[1]


def _number(workbook: openpyxl.Workbook, sheet: str, cell: str) -> Decimal:
    return Decimal(str(workbook[sheet][cell].value))


def test_published_workbook_recalculates_and_reconciles_to_python():
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


def test_published_workbook_has_stable_semantic_digest_and_protected_inputs():
    path = ROOT / WORKBOOK_PATH
    first = semantic_digest(path)
    second = semantic_digest(path)
    assert first == second
    assert len(first) == 64
    assert verify_all_protected_artifacts(ROOT)

