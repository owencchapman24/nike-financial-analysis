import re
from pathlib import Path

import nbformat

from nike_financial_analysis.notebook_runner import execute_notebook


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/01_historical_analysis.ipynb"
EXPECTED_HEADINGS = (
    "# Nike historical financial analysis",
    "## Executive summary",
    "## Data, provenance, and conventions",
    "## Revenue and growth",
    "## Profitability",
    "## Cash generation",
    "## Working capital and liquidity",
    "## Capital structure",
    "## Per-share performance",
    "## Findings and interpretation boundary",
    "## Limitations",
    "## Reproduction",
)


def read_notebook(path: Path = NOTEBOOK):
    return nbformat.read(path, as_version=4)


def test_notebook_has_expected_sections_and_independent_scope_statement():
    notebook = read_notebook()
    markdown = "\n".join(
        "".join(cell.source) for cell in notebook.cells if cell.cell_type == "markdown"
    )

    for heading in EXPECTED_HEADINGS:
        assert heading in markdown
    assert "independent portfolio analysis" in markdown
    assert "historical analysis, not an investment recommendation" in markdown
    assert "educational project" not in markdown.lower()


def test_notebook_code_has_no_network_or_environment_dependency():
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
    ):
        assert forbidden not in code


def test_notebook_relative_links_resolve():
    notebook = read_notebook()
    markdown = "\n".join(
        "".join(cell.source) for cell in notebook.cells if cell.cell_type == "markdown"
    )
    links = re.findall(r"\[[^]]+\]\((\.\./[^)#]+)(?:#[^)]+)?\)", markdown)

    assert links
    for link in links:
        assert (NOTEBOOK.parent / link).resolve().is_file(), link


def test_notebook_executes_top_to_bottom_and_renders_outputs(tmp_path):
    output = tmp_path / "executed.ipynb"
    execute_notebook(NOTEBOOK, output_path=output, repository_root=ROOT)
    notebook = read_notebook(output)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    serialized = nbformat.writes(notebook)

    assert all(cell.execution_count is not None for cell in code_cells)
    assert not any(
        output.get("output_type") == "error"
        for cell in code_cells
        for output in cell.get("outputs", [])
    )
    assert any(
        "image/png" in output.get("data", {})
        for cell in code_cells
        for output in cell.get("outputs", [])
    )
    assert "C:\\Users\\" not in serialized
    assert "SEC_USER_AGENT" not in serialized
    assert all("execution" not in cell.metadata for cell in code_cells)
