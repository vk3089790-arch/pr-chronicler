"""Tests for simulate_merge webhook preparation, HMAC signature generation, and error handling."""

import hashlib
import hmac
import json
import pytest
from unittest.mock import patch

from app.webhook import verify_github_signature
from simulate_merge import (
    build_payload,
    generate_hmac_signature,
    prepare_webhook_request,
)


def test_generate_hmac_signature():
    """Verify HMAC signature calculation format and correctness."""
    secret = "test-secret-key-123"
    body = b'{"action": "closed", "number": 42}'
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    sig = generate_hmac_signature(secret, body)
    assert sig == expected
    assert sig.startswith("sha256=")
    assert len(sig) == 7 + 64


def test_prepare_webhook_request_valid_signature():
    """Verify prepare_webhook_request serializes once, signs exact bytes, and preserves headers."""
    secret = "top-secret-webhook-signing-key"
    payload = build_payload("real-pr", custom_repo="pallets/flask", custom_pr=6168)
    delivery_id = "test-sim-delivery-uuid"
    target_url = "http://localhost:8000/webhook/github"

    req, payload_bytes = prepare_webhook_request(
        url=target_url,
        payload=payload,
        delivery_id=delivery_id,
        secret=secret,
    )

    # 1. Request URL and body
    assert req.full_url == target_url
    assert req.data == payload_bytes
    assert json.loads(payload_bytes.decode("utf-8")) == payload

    # 2. Required GitHub headers preserved
    headers = {k.lower(): v for k, v in req.headers.items()}
    assert headers["content-type"] == "application/json"
    assert headers["x-github-event"] == "pull_request"
    assert headers["x-github-delivery"] == delivery_id
    assert "x-hub-signature-256" in headers

    # 3. Signature verification against backend verifier
    sig_header = headers["x-hub-signature-256"]
    assert verify_github_signature(secret, payload_bytes, sig_header) is True


def test_prepare_webhook_request_missing_secret_raises():
    """Verify clear failure when webhook secret is missing rather than silent bypass."""
    payload = {"action": "closed"}
    with patch("simulate_merge.settings.GITHUB_WEBHOOK_SECRET", None), \
         patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError) as exc:
            prepare_webhook_request(
                url="http://localhost:8000/webhook/github",
                payload=payload,
                delivery_id="delivery-no-secret",
                secret=None,
            )
        assert "Webhook secret is required" in str(exc.value)


def test_prepare_webhook_request_falls_back_to_settings(monkeypatch):
    """Verify that secret is loaded from settings when not passed explicitly via CLI."""
    secret = "settings-loaded-secret"
    monkeypatch.setattr("simulate_merge.settings.GITHUB_WEBHOOK_SECRET", secret)

    payload = {"action": "closed"}
    req, payload_bytes = prepare_webhook_request(
        url="http://localhost:8000/webhook/github",
        payload=payload,
        delivery_id="delivery-settings-secret",
        secret=None,
    )

    sig_header = req.headers["X-hub-signature-256"]
    assert verify_github_signature(secret, payload_bytes, sig_header) is True


def test_no_secret_or_signature_printed_to_stdout(capsys):
    """Verify secrets or signatures are not leaked to console output."""
    secret = "super-confidential-secret-key"
    payload = {"action": "closed"}

    prepare_webhook_request(
        url="http://localhost:8000/webhook/github",
        payload=payload,
        delivery_id="delivery-silent",
        secret=secret,
    )

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert "sha256=" not in captured.out
