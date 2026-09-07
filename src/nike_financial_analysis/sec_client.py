"""Small, respectful HTTP client for public SEC JSON endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
import requests


ALLOWED_SEC_HOSTS = frozenset({"data.sec.gov", "www.sec.gov"})
DEFAULT_CACHE_DIR = Path("data/raw/sec")
PLACEHOLDER_MARKERS = (
    "your-contact",
    "example.com",
    "your-email",
    "placeholder",
)


class SecConfigurationError(ValueError):
    """Raised when the SEC client is missing safe local configuration."""


class SecRequestError(RuntimeError):
    """Raised when an SEC request cannot be completed safely."""


@dataclass(frozen=True)
class SecJsonResponse:
    """Parsed SEC JSON together with retrieval metadata."""

    data: Any
    source_url: str
    retrieved_at: str
    content_sha256: str
    from_cache: bool


class SecClient:
    """Fetch and cache JSON from approved SEC hosts with conservative throttling."""

    def __init__(
        self,
        user_agent: str,
        *,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        minimum_interval_seconds: float = 0.5,
        timeout_seconds: tuple[float, float] = (10.0, 30.0),
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.user_agent = self._validate_user_agent(user_agent)
        if minimum_interval_seconds < 0:
            raise SecConfigurationError("The SEC request interval cannot be negative.")
        if max_retries < 0:
            raise SecConfigurationError("The SEC retry count cannot be negative.")

        self.cache_dir = Path(cache_dir)
        self.minimum_interval_seconds = minimum_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self._last_request_at: float | None = None

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | Path | None = None,
        **kwargs: Any,
    ) -> "SecClient":
        """Build a client from the untracked ``SEC_USER_AGENT`` environment value."""

        load_dotenv(dotenv_path=dotenv_path, override=False)
        user_agent = os.getenv("SEC_USER_AGENT", "")
        return cls(user_agent=user_agent, **kwargs)

    @staticmethod
    def _validate_user_agent(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise SecConfigurationError(
                "SEC_USER_AGENT is missing. Create an ignored .env file from "
                ".env.example and add a descriptive project name and contact address."
            )
        if len(normalized) < 12 or any(
            marker in normalized.casefold() for marker in PLACEHOLDER_MARKERS
        ):
            raise SecConfigurationError(
                "SEC_USER_AGENT is still too short or contains placeholder text. "
                "Update the ignored .env file before making SEC requests."
            )
        return normalized

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SEC_HOSTS:
            raise SecRequestError(
                "SEC requests must use HTTPS and an approved sec.gov host."
            )

    def _cache_path(self, cache_key: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", cache_key):
            raise SecConfigurationError(
                "SEC cache keys may contain only letters, numbers, dots, dashes, "
                "and underscores."
            )
        return self.cache_dir / f"{cache_key}.json"

    def _load_cache(self, cache_path: Path, url: str) -> SecJsonResponse | None:
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SecRequestError(
                f"Cached SEC response is unreadable: {cache_path}. "
                "Remove that cache file and retry."
            ) from exc
        if (
            payload.get("source_url") != url
            or "data" not in payload
            or not payload.get("sha256")
        ):
            raise SecRequestError(
                f"Cached SEC response does not match the requested URL: {cache_path}."
            )
        return SecJsonResponse(
            data=payload["data"],
            source_url=url,
            retrieved_at=str(payload["retrieved_at"]),
            content_sha256=str(payload["sha256"]),
            from_cache=True,
        )

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.minimum_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _retry_delay(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "").strip()
        try:
            return max(float(retry_after), 0.0) if retry_after else 2.0**attempt
        except ValueError:
            return 2.0**attempt

    def get_json(
        self,
        url: str,
        *,
        cache_key: str,
        force_refresh: bool = False,
    ) -> SecJsonResponse:
        """Return JSON from cache or the SEC, retrying only temporary failures."""

        self._validate_url(url)
        cache_path = self._cache_path(cache_key)
        if not force_refresh:
            cached = self._load_cache(cache_path, url)
            if cached is not None:
                return cached

        retryable_statuses = {429, 500, 502, 503, 504}
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(2.0**attempt)
                continue

            if response.status_code == 200:
                try:
                    data = response.json()
                except requests.JSONDecodeError as exc:
                    raise SecRequestError(
                        f"SEC returned invalid JSON for {url}."
                    ) from exc
                retrieved_at = datetime.now(UTC).isoformat()
                content_sha256 = hashlib.sha256(response.content).hexdigest()
                cache_payload = {
                    "source_url": url,
                    "retrieved_at": retrieved_at,
                    "response_headers": {
                        "content_type": response.headers.get("Content-Type"),
                        "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified"),
                    },
                    "sha256": content_sha256,
                    "data": data,
                }
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = cache_path.with_suffix(".json.tmp")
                temporary_path.write_text(
                    json.dumps(cache_payload, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                temporary_path.replace(cache_path)
                return SecJsonResponse(
                    data=data,
                    source_url=url,
                    retrieved_at=retrieved_at,
                    content_sha256=content_sha256,
                    from_cache=False,
                )

            if response.status_code in retryable_statuses and attempt < self.max_retries:
                time.sleep(self._retry_delay(response, attempt))
                continue
            raise SecRequestError(
                f"SEC request failed with HTTP {response.status_code} for {url}."
            )

        raise SecRequestError(
            f"SEC request failed after {self.max_retries + 1} attempts for {url}. "
            "Check the network connection and try again later."
        ) from last_error
