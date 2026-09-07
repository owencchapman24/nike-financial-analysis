import csv
import hashlib
import re
import struct
from pathlib import Path

from nike_financial_analysis.analysis import (
    EXPECTED_FISCAL_YEARS,
    PROTECTED_PHASE2_HASHES,
    generate_artifacts,
    verify_phase2_hashes,
)
from nike_financial_analysis.charts import CHART_FILENAMES


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_text_chunks(path: Path) -> bytes:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    text = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        if kind in {b"tEXt", b"zTXt", b"iTXt"}:
            text.extend(payload)
        offset += 12 + length
        if kind == b"IEND":
            break
    return bytes(text)


def test_phase2_outputs_retain_approved_hashes():
    verified = verify_phase2_hashes(ROOT)

    assert verified == {
        path.as_posix(): expected for path, expected in PROTECTED_PHASE2_HASHES.items()
    }


def test_artifact_build_is_complete_and_deterministic(tmp_path):
    first_tables = tmp_path / "first/tables"
    first_charts = tmp_path / "first/charts"
    second_tables = tmp_path / "second/tables"
    second_charts = tmp_path / "second/charts"

    first = generate_artifacts(ROOT, tables_dir=first_tables, charts_dir=first_charts)
    second = generate_artifacts(ROOT, tables_dir=second_tables, charts_dir=second_charts)

    assert first["summary_rows"] == 5
    assert first["kpi_rows"] == 205
    assert tuple(path.name for path in first["chart_paths"]) == CHART_FILENAMES
    for first_path, second_path in zip(
        (*first["table_paths"], *first["chart_paths"]),
        (*second["table_paths"], *second["chart_paths"]),
        strict=True,
    ):
        assert first_path.stat().st_size > 0
        assert sha256(first_path) == sha256(second_path)

    with first["table_paths"][0].open(encoding="utf-8", newline="") as handle:
        summary = list(csv.DictReader(handle))
    with first["table_paths"][1].open(encoding="utf-8", newline="") as handle:
        kpis = list(csv.DictReader(handle))
    assert tuple(row["fiscal_year"] for row in summary) == EXPECTED_FISCAL_YEARS
    assert set(row["fiscal_year"] for row in kpis) == set(EXPECTED_FISCAL_YEARS)


def test_generated_artifacts_have_no_runtime_or_private_metadata(tmp_path):
    result = generate_artifacts(
        ROOT,
        tables_dir=tmp_path / "tables",
        charts_dir=tmp_path / "charts",
    )
    forbidden = (b"C:\\Users\\", b"SEC_USER_AGENT", b"@", b"Creation Time", b"Date")

    for path in result["table_paths"]:
        content = path.read_bytes()
        assert not any(token in content for token in forbidden)
    for path in result["chart_paths"]:
        metadata = png_text_chunks(path)
        assert b"nike-financial-analysis" in metadata
        assert not any(token in metadata for token in forbidden)


def test_readme_relative_links_resolve():
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]*\]\(([^)]+)\)", content)

    assert links
    for link in links:
        if "://" in link or link.startswith("#"):
            continue
        target = link.split("#", 1)[0]
        assert (ROOT / target).exists(), link
