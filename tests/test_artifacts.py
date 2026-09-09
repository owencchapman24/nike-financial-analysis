import csv
import base64
import hashlib
import io
import json
import re
import struct
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from nike_financial_analysis.artifact_integrity import (
    ArtifactIntegrityError,
    semantic_notebook_sha256,
    semantic_png_sha256,
)
from nike_financial_analysis.analysis import (
    EXPECTED_FISCAL_YEARS,
    PROTECTED_PHASE2_HASHES,
    generate_artifacts,
    hash_matches_expected,
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


def test_protected_text_hashes_allow_only_line_ending_normalization(tmp_path):
    path = tmp_path / "protected.csv"
    crlf_payload = b"metric,value\r\nrevenue,46398\r\n"
    expected = hashlib.sha256(crlf_payload).hexdigest()

    path.write_bytes(crlf_payload.replace(b"\r\n", b"\n"))
    assert hash_matches_expected(path, expected)

    path.write_bytes(crlf_payload.replace(b"\r\n", b"\r"))
    assert not hash_matches_expected(path, expected)

    path.write_bytes(b"metric,value\nrevenue,46399\n")
    assert not hash_matches_expected(path, expected)


def _png_bytes(
    *,
    pixels=((10, 20, 30, 255), (40, 50, 60, 255)),
    size=(2, 1),
    mode="RGBA",
    compress_level=6,
    metadata=None,
):
    image = Image.new(mode, size)
    image.putdata(pixels)
    output = io.BytesIO()
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("Software", "nike-financial-analysis")
    if metadata:
        for key, value in metadata.items():
            pnginfo.add_text(key, value)
    image.save(output, format="PNG", compress_level=compress_level, pnginfo=pnginfo)
    return output.getvalue()


def test_semantic_png_accepts_recompression_and_rejects_visual_changes(tmp_path):
    low = tmp_path / "low.png"
    high = tmp_path / "high.png"
    low.write_bytes(_png_bytes(compress_level=0))
    high.write_bytes(_png_bytes(compress_level=9))

    expected = semantic_png_sha256(low)
    assert low.read_bytes() != high.read_bytes()
    assert semantic_png_sha256(high) == expected
    assert hash_matches_expected(high, expected)

    pixel = tmp_path / "pixel.png"
    pixel.write_bytes(
        _png_bytes(pixels=((11, 20, 30, 255), (40, 50, 60, 255)))
    )
    dimension = tmp_path / "dimension.png"
    dimension.write_bytes(
        _png_bytes(
            pixels=((10, 20, 30, 255), (40, 50, 60, 255), (70, 80, 90, 255)),
            size=(3, 1),
        )
    )
    color_mode = tmp_path / "mode.png"
    color_mode.write_bytes(
        _png_bytes(pixels=((10, 20, 30), (40, 50, 60)), mode="RGB")
    )
    assert semantic_png_sha256(pixel) != expected
    assert semantic_png_sha256(dimension) != expected
    assert semantic_png_sha256(color_mode) != expected


@pytest.mark.parametrize("payload", [b"not png", b"\x89PNG\r\n\x1a\ntruncated"])
def test_semantic_png_rejects_invalid_content(tmp_path, payload):
    path = tmp_path / "invalid.png"
    path.write_bytes(payload)
    with pytest.raises(ArtifactIntegrityError, match="valid PNG|Expected PNG"):
        semantic_png_sha256(path)
    assert not hash_matches_expected(path, "0" * 64)


def test_png_metadata_allowlist_rejects_free_form_content(tmp_path):
    path = tmp_path / "metadata.png"
    path.write_bytes(_png_bytes(metadata={"Comment": "temporary path"}))
    with pytest.raises(ArtifactIntegrityError, match="unexpected metadata"):
        semantic_png_sha256(path)


def _notebook(path: Path, png: bytes, *, image_as_list=False) -> None:
    encoded = base64.b64encode(png).decode("ascii")
    payload = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": ["# Finding\n"]},
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "source": ["print('table')\n"],
                "outputs": [
                    {"name": "stdout", "output_type": "stream", "text": ["table\n"]},
                    {
                        "data": {"image/png": [encoded] if image_as_list else encoded},
                        "metadata": {},
                        "output_type": "display_data",
                    },
                ],
            },
        ],
        "metadata": {"kernelspec": {"name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def test_notebook_fingerprint_normalizes_only_embedded_png_containers(tmp_path):
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"
    _notebook(first, _png_bytes(compress_level=0))
    _notebook(second, _png_bytes(compress_level=9), image_as_list=True)
    expected = semantic_notebook_sha256(first)
    assert semantic_notebook_sha256(second) == expected
    assert hash_matches_expected(second, expected)

    payload = json.loads(second.read_text(encoding="utf-8"))
    for field, value in (
        ((0, "source"), ["# Changed finding\n"]),
        ((1, "source"), ["print('changed')\n"]),
        ((1, "text"), ["changed table\n"]),
    ):
        changed = json.loads(json.dumps(payload))
        cell, target = field
        if target == "text":
            changed["cells"][cell]["outputs"][0][target] = value
        else:
            changed["cells"][cell][target] = value
        candidate = tmp_path / f"changed-{target}-{cell}.ipynb"
        candidate.write_text(json.dumps(changed), encoding="utf-8")
        assert semantic_notebook_sha256(candidate) != expected

    changed_pixel = tmp_path / "changed-pixel.ipynb"
    _notebook(
        changed_pixel,
        _png_bytes(pixels=((11, 20, 30, 255), (40, 50, 60, 255))),
    )
    assert semantic_notebook_sha256(changed_pixel) != expected


def test_non_png_binary_protection_remains_byte_exact(tmp_path):
    path = tmp_path / "model.xlsx"
    path.write_bytes(b"binary-one")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert hash_matches_expected(path, expected)
    path.write_bytes(b"binary-two")
    assert not hash_matches_expected(path, expected)


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

    for path in first["table_paths"]:
        assert b"\r\n" not in path.read_bytes()

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
