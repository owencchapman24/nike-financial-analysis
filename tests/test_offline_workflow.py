"""Exercise the documented offline workflow in an isolated tracked-file copy."""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, PngImagePlugin

from nike_financial_analysis.artifact_integrity import (
    semantic_notebook_sha256,
    semantic_png_sha256,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_tracked_files(destination: Path) -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def _block_external_network(directory: Path) -> None:
    directory.mkdir(parents=True)
    (directory / "sitecustomize.py").write_text(
        """import ipaddress
import socket

_connect = socket.socket.connect

def _local(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

def connect(self, address):
    if isinstance(address, tuple) and not _local(address[0]):
        raise RuntimeError("external network disabled by offline workflow test")
    return _connect(self, address)

socket.socket.connect = connect
_create_connection = socket.create_connection

def create_connection(address, *args, **kwargs):
    if not _local(address[0]):
        raise RuntimeError("external network disabled by offline workflow test")
    return _create_connection(address, *args, **kwargs)

socket.create_connection = create_connection
""",
        encoding="utf-8",
    )


def _run_entrypoint(
    repository: Path, blocker: Path, module: str, arguments: list[str]
) -> None:
    environment = os.environ.copy()
    environment.pop("SEC_USER_AGENT", None)
    environment.pop("DOTENV_PATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(blocker), str(repository / "src"))
    )
    code = (
        "import sys; "
        f"from {module} import main; "
        f"sys.argv={['workflow', *arguments]!r}; "
        "main()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _recompress_png(path: Path) -> None:
    with Image.open(path) as image:
        image.load()
        output = io.BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Software", "nike-financial-analysis")
        image.save(
            output,
            format="PNG",
            compress_level=0,
            pnginfo=metadata,
            dpi=(150, 150),
        )
    path.write_bytes(output.getvalue())


def _recompress_first_notebook_png(path: Path) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        for output in cell.get("outputs", []):
            data = output.get("data", {})
            if "image/png" not in data:
                continue
            encoded = data["image/png"]
            payload = base64.b64decode(
                "".join(encoded) if isinstance(encoded, list) else encoded
            )
            temporary = path.with_suffix(".embedded.png")
            temporary.write_bytes(payload)
            _recompress_png(temporary)
            data["image/png"] = base64.b64encode(temporary.read_bytes()).decode("ascii")
            temporary.unlink()
            path.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
            return
    raise AssertionError(f"No embedded PNG found in {path.name}")


def test_documented_offline_workflow_survives_container_only_changes(tmp_path):
    repository = tmp_path / "repository"
    blocker = tmp_path / "network-blocker"
    _copy_tracked_files(repository)
    _block_external_network(blocker)
    assert not (repository / ".env").exists()
    assert not (repository / "data/raw/sec").exists()

    _run_entrypoint(repository, blocker, "nike_financial_analysis.analysis", [])
    _run_entrypoint(
        repository,
        blocker,
        "nike_financial_analysis.notebook_runner",
        ["notebooks/01_historical_analysis.ipynb", "--in-place"],
    )
    _recompress_png(repository / "outputs/charts/01_revenue_and_growth.png")
    _recompress_first_notebook_png(repository / "notebooks/01_historical_analysis.ipynb")

    _run_entrypoint(repository, blocker, "nike_financial_analysis.forecast", [])
    _run_entrypoint(
        repository,
        blocker,
        "nike_financial_analysis.notebook_runner",
        ["notebooks/02_scenario_forecast.ipynb", "--in-place"],
    )
    _recompress_png(repository / "outputs/charts/06_forecast_revenue.png")
    _recompress_first_notebook_png(repository / "notebooks/02_scenario_forecast.ipynb")
    _run_entrypoint(repository, blocker, "nike_financial_analysis.valuation", [])

    for relative in (
        "outputs/charts/01_revenue_and_growth.png",
        "outputs/charts/06_forecast_revenue.png",
        "outputs/charts/10_scenario_valuation.png",
    ):
        assert semantic_png_sha256(repository / relative) == semantic_png_sha256(
            ROOT / relative
        )
    for relative in (
        "notebooks/01_historical_analysis.ipynb",
        "notebooks/02_scenario_forecast.ipynb",
    ):
        assert semantic_notebook_sha256(repository / relative) == semantic_notebook_sha256(
            ROOT / relative
        )

    generated_csvs = (
        *(repository / "outputs/tables").glob("*.csv"),
        *(repository / "outputs/model_exports").glob("*.csv"),
    )
    assert generated_csvs
    for path in generated_csvs:
        payload = path.read_bytes()
        assert payload.endswith(b"\n")
        assert b"\r\n" not in payload
