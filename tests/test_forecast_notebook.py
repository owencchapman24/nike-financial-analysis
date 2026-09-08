import re
from pathlib import Path

import nbformat

from nike_financial_analysis.notebook_runner import execute_notebook


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/02_scenario_forecast.ipynb"
EXPECTED_HEADINGS = (
    "# Nike FY2027-FY2031 operating scenarios",
    "## Scope and source boundary",
    "## Forecast methodology and conventions",
    "## Documented scenario drivers",
    "## Revenue and derived operating margin",
    "## Key scenario outputs",
    "## Operating working capital and FY2027 FCFF bridge",
    "## FCFF and reinvestment",
    "## Tax, leases, and interpretation limits",
    "## Reproduction",
)


def read_notebook(path: Path = NOTEBOOK):
    return nbformat.read(path, as_version=4)


def test_forecast_notebook_scope_sections_and_disclosures():
    notebook = read_notebook()
    markdown = "\n".join(
        "".join(cell.source) for cell in notebook.cells if cell.cell_type == "markdown"
    )
    for heading in EXPECTED_HEADINGS:
        assert heading in markdown
    for required in (
        "September 7, 2026",
        "210-basis-point",
        "40.8%",
        "not Nike-reported EBIT",
        "not an investment recommendation",
        "USD 5,507 million",
        "not purely operating-driven",
        "low-20% range",
        "not full-year company guidance",
    ):
        assert required in markdown


def test_forecast_notebook_has_no_network_environment_or_valuation_code():
    notebook = read_notebook()
    code = "\n".join(
        "".join(cell.source) for cell in notebook.cells if cell.cell_type == "code"
    ).lower()
    for forbidden in (
        "requests",
        "sec_client",
        "urlopen",
        "http://",
        "https://",
        "dotenv",
        "sec_user_agent",
        ".env",
        "wacc",
        "terminal_value",
        "present_value",
    ):
        assert forbidden not in code


def test_forecast_notebook_relative_links_resolve():
    notebook = read_notebook()
    markdown = "\n".join(
        "".join(cell.source) for cell in notebook.cells if cell.cell_type == "markdown"
    )
    links = re.findall(r"\[[^]]+\]\((\.\./[^)#]+)(?:#[^)]+)?\)", markdown)
    assert links
    for link in links:
        assert (NOTEBOOK.parent / link).resolve().is_file(), link


def test_forecast_notebook_executes_cleanly_and_renders_figures(tmp_path):
    output = tmp_path / "forecast.ipynb"
    execute_notebook(NOTEBOOK, output_path=output, repository_root=ROOT)
    notebook = read_notebook(output)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    serialized = nbformat.writes(notebook)
    assert all(cell.execution_count is not None for cell in code_cells)
    assert not any(
        item.get("output_type") == "error"
        for cell in code_cells
        for item in cell.get("outputs", [])
    )
    assert sum(
        "image/png" in item.get("data", {})
        for cell in code_cells
        for item in cell.get("outputs", [])
    ) == 4
    key_output = next(cell for cell in code_cells if cell.id == "key-output-table")
    rendered_key_output = "".join(
        item.get("data", {}).get("text/plain", "") for item in key_output.outputs
    )
    assert "Revenue (USDm)" in rendered_key_output
    assert "Derived operating margin" in rendered_key_output
    assert "FCFF margin" in rendered_key_output
    assert "C:\\Users\\" not in serialized
    assert "SEC_USER_AGENT" not in serialized
