from __future__ import annotations

import pytest

from app.core.ssrf import SsrfError, SsrfPolicy, validate_endpoint


def _policy(*hosts: str) -> SsrfPolicy:
    return SsrfPolicy(allowed_private_hosts=frozenset(hosts))


def test_public_https_is_allowed_and_plain_http_is_not():
    validate_endpoint(
        "https://models.example/v1",
        _policy(),
        resolve=lambda host, port: ["1.1.1.1"],
    )
    with pytest.raises(SsrfError):
        validate_endpoint(
            "http://models.example/v1",
            _policy(),
            resolve=lambda host, port: ["1.1.1.1"],
        )


def test_private_hosts_require_an_explicit_allow_list():
    with pytest.raises(SsrfError):
        validate_endpoint("http://127.0.0.1:11434/v1", _policy(), resolve=lambda host, port: [host])
    validate_endpoint(
        "http://127.0.0.1:11434/v1",
        _policy("127.0.0.1"),
        resolve=lambda host, port: ["127.0.0.1"],
    )


def test_metadata_and_unsafe_urls_stay_blocked():
    with pytest.raises(SsrfError):
        validate_endpoint(
            "http://169.254.169.254/latest/meta-data",
            _policy("169.254.169.254"),
            resolve=lambda host, port: ["169.254.169.254"],
        )
    with pytest.raises(SsrfError):
        validate_endpoint(
            "https://metadata.google.internal/",
            _policy("metadata.google.internal"),
            resolve=lambda host, port: ["169.254.169.254"],
        )
    with pytest.raises(SsrfError):
        validate_endpoint("file:///etc/passwd", _policy(), resolve=lambda host, port: [])
    with pytest.raises(SsrfError):
        validate_endpoint(
            "https://user:secret@models.example/v1",
            _policy(),
            resolve=lambda host, port: ["1.1.1.1"],
        )


def test_redirect_targets_are_checked_again():
    with pytest.raises(SsrfError):
        validate_endpoint(
            "http://169.254.169.254/latest",
            _policy("model.internal"),
            resolve=lambda host, port: ["169.254.169.254"],
        )
