"""Execute a project notebook reproducibly with nbclient."""

from __future__ import annotations

import argparse
from pathlib import Path
import warnings

import nbformat
from nbclient import NotebookClient

from nike_financial_analysis.analysis import find_repository_root


def execute_notebook(
    notebook_path: Path,
    *,
    output_path: Path,
    repository_root: Path | None = None,
) -> Path:
    """Execute a notebook from the repository root and remove timing metadata."""

    root = repository_root or find_repository_root(notebook_path.parent)
    input_path = notebook_path if notebook_path.is_absolute() else root / notebook_path
    destination = output_path if output_path.is_absolute() else root / output_path
    if not input_path.is_file():
        raise FileNotFoundError(f"Notebook not found: {notebook_path.name}")

    notebook = nbformat.read(input_path, as_version=4)
    for index, cell in enumerate(notebook.cells):
        cell["id"] = cell.get("id", f"cell-{index:02d}")
    client = NotebookClient(
        notebook,
        timeout=180,
        kernel_name="python3",
        resources={"metadata": {"path": str(root)}},
        record_timing=False,
        allow_errors=False,
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=(
                "Proactor event loop does not implement add_reader family of methods"
            ),
            category=RuntimeWarning,
        )
        executed = client.execute()
    for cell in executed.cells:
        cell.metadata.pop("execution", None)
    destination.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(executed, destination)
    return destination


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute a project notebook from the repository root."
    )
    parser.add_argument("notebook", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--in-place",
        action="store_true",
        help="Replace the notebook with its deterministically executed form.",
    )
    destination.add_argument(
        "--output",
        type=Path,
        help="Write the executed notebook to a separate path.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = find_repository_root(Path.cwd())
    notebook = args.notebook if args.notebook.is_absolute() else root / args.notebook
    output = notebook if args.in_place else args.output
    if output is None:
        raise ValueError("An output path is required.")
    execute_notebook(notebook, output_path=output, repository_root=root)
    print("Notebook executed successfully from the repository root.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
