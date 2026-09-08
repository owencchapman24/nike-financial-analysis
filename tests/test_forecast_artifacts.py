import csv
import hashlib
import re
import struct
from decimal import Decimal
from pathlib import Path

from nike_financial_analysis.analysis import verify_phase2_hashes
from nike_financial_analysis.charts import FORECAST_CHART_FILENAMES
from nike_financial_analysis.forecast import (
    FORECAST_TABLE_FILENAMES,
    generate_forecast_artifacts,
    verify_phase3_hashes,
)


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


def test_forecast_build_is_complete_and_deterministic(tmp_path):
    first = generate_forecast_artifacts(
        ROOT, tables_dir=tmp_path / "first/tables", charts_dir=tmp_path / "first/charts"
    )
    second = generate_forecast_artifacts(
        ROOT, tables_dir=tmp_path / "second/tables", charts_dir=tmp_path / "second/charts"
    )
    assert first["assumption_rows"] == 105
    assert first["forecast_rows"] == 15
    assert tuple(path.name for path in first["table_paths"]) == FORECAST_TABLE_FILENAMES
    assert tuple(path.name for path in first["chart_paths"]) == FORECAST_CHART_FILENAMES
    for left, right in zip(
        (*first["table_paths"], *first["chart_paths"]),
        (*second["table_paths"], *second["chart_paths"]),
        strict=True,
    ):
        assert left.stat().st_size > 0
        assert sha256(left) == sha256(right)

    with first["table_paths"][0].open(encoding="utf-8", newline="") as handle:
        long_rows = list(csv.DictReader(handle))
    assert {row["scenario"] for row in long_rows} == {"actual", "base", "bull", "bear"}
    assert {row["period_class"] for row in long_rows} == {"actual", "forecast"}


def test_protected_prior_phase_hashes_are_unchanged():
    assert verify_phase2_hashes(ROOT)
    assert verify_phase3_hashes(ROOT)


def test_forecast_artifacts_contain_no_private_or_runtime_metadata(tmp_path):
    result = generate_forecast_artifacts(
        ROOT, tables_dir=tmp_path / "tables", charts_dir=tmp_path / "charts"
    )
    forbidden = (b"C:\\Users\\", b"SEC_USER_AGENT", b"@", b"Creation Time", b"Date")
    for path in result["table_paths"]:
        assert not any(token in path.read_bytes() for token in forbidden)
    for path in result["chart_paths"]:
        metadata = png_text_chunks(path)
        assert b"nike-financial-analysis" in metadata
        assert not any(token in metadata for token in forbidden)


def test_readme_phase4_links_resolve():
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]*\]\(([^)]+)\)", content)
    for link in links:
        if "://" in link or link.startswith("#"):
            continue
        assert (ROOT / link.split("#", 1)[0]).exists(), link


def test_scenario_summary_is_presentation_rounded_with_metric_specific_notes(tmp_path):
    result = generate_forecast_artifacts(
        ROOT, tables_dir=tmp_path / "tables", charts_dir=tmp_path / "charts"
    )
    summary_path = next(
        path for path in result["table_paths"] if path.name == "scenario_forecast_summary.csv"
    )
    with summary_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 60
    for row in rows:
        quantum = Decimal("0.001") if row["unit"] == "decimal" else Decimal("1")
        for column in ("FY2026_actual", "FY2027", "FY2028", "FY2029", "FY2030", "FY2031"):
            if row[column]:
                assert Decimal(row[column]).as_tuple().exponent == quantum.as_tuple().exponent
    assert len({row["notes"] for row in rows if row["notes"]}) >= 10
    assert "authoritative precision" in rows[0]["presentation_rounding"]


def test_public_phase4_material_avoids_internal_owner_approval_language():
    paths = (
        ROOT / "README.md",
        ROOT / "docs/forecast_methodology.md",
        ROOT / "docs/methodology.md",
        ROOT / "docs/data_dictionary.md",
        ROOT / "docs/limitations.md",
        ROOT / "docs/scenario_rationale.md",
        ROOT / "notebooks/02_scenario_forecast.ipynb",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert "owner-approved" not in text, path
        assert "owner approved" not in text, path
