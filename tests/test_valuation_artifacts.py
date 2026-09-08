import csv
import hashlib
import struct
from pathlib import Path

from nike_financial_analysis.charts import VALUATION_CHART_FILENAMES
from nike_financial_analysis.valuation import (
    VALUATION_EXPORT_FILENAMES,
    generate_valuation_artifacts,
    verify_phase4_hashes,
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


def test_valuation_artifacts_are_complete_and_deterministic(tmp_path):
    first = generate_valuation_artifacts(
        ROOT,
        exports_dir=tmp_path / "first/exports",
        charts_dir=tmp_path / "first/charts",
    )
    second = generate_valuation_artifacts(
        ROOT,
        exports_dir=tmp_path / "second/exports",
        charts_dir=tmp_path / "second/charts",
    )
    assert tuple(path.name for path in first["table_paths"]) == VALUATION_EXPORT_FILENAMES
    assert tuple(path.name for path in first["chart_paths"]) == VALUATION_CHART_FILENAMES
    for left, right in zip(
        (*first["table_paths"], *first["chart_paths"]),
        (*second["table_paths"], *second["chart_paths"]),
        strict=True,
    ):
        assert left.stat().st_size > 0
        assert sha256(left) == sha256(right)

    expected_rows = {
        "wacc_build.csv": 38,
        "valuation_cash_flows.csv": 18,
        "valuation_summary.csv": 3,
        "dcf_sensitivity.csv": 25,
        "valuation_validation_summary.csv": len(first["model"].checks),
    }
    for path in first["table_paths"]:
        with path.open(encoding="utf-8", newline="") as handle:
            assert len(list(csv.DictReader(handle))) == expected_rows[path.name]


def test_valuation_artifacts_exclude_private_and_runtime_metadata(tmp_path):
    result = generate_valuation_artifacts(
        ROOT, exports_dir=tmp_path / "exports", charts_dir=tmp_path / "charts"
    )
    forbidden = (b"C:\\Users\\", b"SEC_USER_AGENT", b"Creation Time", b".env")
    for path in result["table_paths"]:
        assert not any(token in path.read_bytes() for token in forbidden)
    for path in result["chart_paths"]:
        metadata = png_text_chunks(path)
        assert b"nike-financial-analysis" in metadata
        assert not any(token in metadata for token in forbidden)


def test_protected_phase4_artifacts_remain_unchanged():
    assert verify_phase4_hashes(ROOT)
