import json

import pytest

from nike_financial_analysis.sec_client import (
    SecClient,
    SecConfigurationError,
    SecRequestError,
)


class FakeResponse:
    status_code = 200
    headers = {
        "Content-Type": "application/json",
        "ETag": '"test-etag"',
    }
    content = b'{"verified": true}'

    def json(self):
        return {"verified": True}


class RecordingSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return FakeResponse()


class FailingSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, timeout):
        raise AssertionError("Network should not be used for a valid cache hit")


def test_from_env_rejects_missing_user_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)

    with pytest.raises(SecConfigurationError, match="missing"):
        SecClient.from_env(dotenv_path=tmp_path / "missing.env")


def test_rejects_placeholder_user_agent(tmp_path):
    with pytest.raises(SecConfigurationError, match="placeholder"):
        SecClient(
            "Nike project your-contact-address@example.com",
            cache_dir=tmp_path,
        )


def test_rejects_non_sec_url(tmp_path):
    client = SecClient("Nike analysis analyst@domain.test", cache_dir=tmp_path)

    with pytest.raises(SecRequestError, match="approved sec.gov host"):
        client.get_json("https://example.org/data.json", cache_key="invalid")


def test_successful_response_is_cached_and_reused(tmp_path):
    url = "https://data.sec.gov/submissions/CIK0000000001.json"
    recording_session = RecordingSession()
    client = SecClient(
        "Nike analysis analyst@domain.test",
        cache_dir=tmp_path,
        minimum_interval_seconds=0,
        session=recording_session,
    )

    first = client.get_json(url, cache_key="test_response")

    assert first.data == {"verified": True}
    assert first.from_cache is False
    assert len(recording_session.calls) == 1
    cache_payload = json.loads(
        (tmp_path / "test_response.json").read_text(encoding="utf-8")
    )
    assert cache_payload["source_url"] == url
    assert cache_payload["sha256"]
    assert first.content_sha256 == cache_payload["sha256"]

    cached_client = SecClient(
        "Nike analysis analyst@domain.test",
        cache_dir=tmp_path,
        session=FailingSession(),
    )
    second = cached_client.get_json(url, cache_key="test_response")

    assert second.data == {"verified": True}
    assert second.from_cache is True
    assert second.retrieved_at == first.retrieved_at
    assert second.content_sha256 == first.content_sha256
