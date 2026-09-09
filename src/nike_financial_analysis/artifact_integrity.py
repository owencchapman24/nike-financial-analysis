"""Artifact-specific fingerprints for reproducible project outputs."""

from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


PNG_DIGEST_VERSION = b"PNG-SEMANTIC-v1\0"
NOTEBOOK_DIGEST_VERSION = b"IPYNB-SEMANTIC-v1\0"
ALLOWED_PNG_METADATA = frozenset({"Software", "dpi"})
EXPECTED_SOFTWARE = "nike-financial-analysis"


class ArtifactIntegrityError(ValueError):
    """Raised when an artifact cannot be safely fingerprinted."""


def raw_sha256(path: Path) -> str:
    """Return the SHA-256 of a file's exact bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _png_components(payload: bytes) -> tuple[int, int, str, bytes]:
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG":
                raise ArtifactIntegrityError("Expected PNG content.")
            image.load()
            unexpected = set(image.info) - ALLOWED_PNG_METADATA
            if unexpected:
                raise ArtifactIntegrityError(
                    "PNG contains unexpected metadata fields: "
                    + ", ".join(sorted(unexpected))
                )
            software = image.info.get("Software")
            if software is not None and software != EXPECTED_SOFTWARE:
                raise ArtifactIntegrityError("PNG Software metadata is not project-generic.")
            dpi = image.info.get("dpi")
            if dpi is not None and (
                not isinstance(dpi, tuple)
                or len(dpi) != 2
                or not all(isinstance(value, (int, float)) for value in dpi)
            ):
                raise ArtifactIntegrityError("PNG DPI metadata is not numeric.")
            return image.width, image.height, image.mode, image.tobytes()
    except (OSError, UnidentifiedImageError) as exc:
        raise ArtifactIntegrityError("Artifact is not a valid PNG image.") from exc


def semantic_png_sha256_bytes(payload: bytes) -> str:
    """Fingerprint decoded PNG pixels, dimensions, and color mode."""

    width, height, mode, pixels = _png_components(payload)
    identity = (
        PNG_DIGEST_VERSION
        + str(width).encode("ascii")
        + b"x"
        + str(height).encode("ascii")
        + b"\0"
        + mode.encode("ascii")
        + b"\0"
        + pixels
    )
    return hashlib.sha256(identity).hexdigest()


def semantic_png_sha256(path: Path) -> str:
    """Return the semantic PNG fingerprint for a file."""

    return semantic_png_sha256_bytes(path.read_bytes())


def _canonical_notebook_value(value: Any) -> Any:
    if isinstance(value, dict):
        canonical: dict[str, Any] = {}
        for key, item in value.items():
            if key == "image/png":
                encoded = "".join(item) if isinstance(item, list) else item
                if not isinstance(encoded, str):
                    raise ArtifactIntegrityError("Notebook PNG output is not base64 text.")
                try:
                    payload = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError) as exc:
                    raise ArtifactIntegrityError(
                        "Notebook contains an invalid base64 PNG output."
                    ) from exc
                canonical[key] = {
                    "semantic_png_sha256": semantic_png_sha256_bytes(payload)
                }
            else:
                canonical[key] = _canonical_notebook_value(item)
        return canonical
    if isinstance(value, list):
        return [_canonical_notebook_value(item) for item in value]
    return value


def semantic_notebook_sha256(path: Path) -> str:
    """Fingerprint notebook content while normalizing embedded PNG containers."""

    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError("Artifact is not valid notebook JSON.") from exc
    canonical = json.dumps(
        _canonical_notebook_value(notebook),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(NOTEBOOK_DIGEST_VERSION + canonical).hexdigest()


def hash_matches_expected(path: Path, expected: str) -> bool:
    """Apply the artifact's strictest appropriate identity rule."""

    try:
        suffix = path.suffix.lower()
        if suffix == ".png":
            return semantic_png_sha256(path) == expected
        if suffix == ".ipynb":
            return semantic_notebook_sha256(path) == expected
        payload = path.read_bytes()
        candidates = {hashlib.sha256(payload).hexdigest()}
        if suffix in {".csv", ".md", ".py", ".toml"}:
            lf_payload = payload.replace(b"\r\n", b"\n")
            if b"\r" not in lf_payload:
                crlf_payload = lf_payload.replace(b"\n", b"\r\n")
                candidates.add(hashlib.sha256(lf_payload).hexdigest())
                candidates.add(hashlib.sha256(crlf_payload).hexdigest())
        return expected in candidates
    except (ArtifactIntegrityError, OSError):
        return False
