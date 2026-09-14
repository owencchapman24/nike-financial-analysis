"""Pytest configuration for portable and desktop-Excel test separation."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the explicit opt-in flag for tests that launch desktop Excel."""

    parser.addoption(
        "--run-excel-integration",
        action="store_true",
        default=False,
        help="run Windows desktop-Excel/COM integration tests",
    )


def _excel_prerequisite_errors() -> list[str]:
    errors: list[str] = []
    if os.name != "nt":
        errors.append("Windows is required")
        return errors
    if shutil.which("powershell.exe") is None:
        errors.append("powershell.exe is not available on PATH")
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID"
        ):
            pass
    except (ImportError, FileNotFoundError, OSError):
        errors.append("Microsoft Excel is not registered for COM automation")
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "recalculate_workbook.ps1"
    )
    if not script.is_file():
        errors.append("scripts/recalculate_workbook.ps1 is missing")
    return errors


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip Excel integration by default and fail clearly on an invalid opt-in."""

    integration_items = [
        item for item in items if item.get_closest_marker("excel_integration")
    ]
    if not integration_items:
        return
    if not config.getoption("--run-excel-integration"):
        reason = "requires --run-excel-integration and Windows desktop Excel"
        marker = pytest.mark.skip(reason=reason)
        for item in integration_items:
            item.add_marker(marker)
        return
    errors = _excel_prerequisite_errors()
    if errors:
        raise pytest.UsageError(
            "Excel integration was explicitly requested, but prerequisites are "
            f"unavailable: {'; '.join(errors)}. Install desktop Excel and ensure "
            "Windows PowerShell is available, or omit --run-excel-integration."
        )
