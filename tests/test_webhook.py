"""Tests for FastAPI webhook endpoint filtering, signature validation, and routing."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import DatabaseManager
from app.main import app
from app.models import ReflectionOutput
from app.webhook import pipeline_service, verify_github_signature


@pytest.fixture
def test_client(mock_settings, tmp_path):
    """TestClient configured with fresh SQLite database and application lifespan."""
    test_db_path = str(tmp_path / "webhook_test.db")
    pipeline_service.db = DatabaseManager(test_db_path)
    with TestClient(app) as client:
        yield client


def test_signature_verification_helper():
    """Verify HMAC SHA-256 computation and matching."""
    secret = "super-secret-key-123"
    body = b'{"action": "closed"}'

    # Valid signature
    valid_sig = f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"
    assert verify_github_signature(secret, body, valid_sig) is True

    # Invalid signature
    invalid_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
    assert verify_github_signature(secret, body, invalid_sig) is False

    # Missing sha256= prefix
    assert verify_github_signature(secret, body, "invalid-prefix") is False

    # None or empty header
    assert verify_github_signature(secret, body, None) is False


def test_signature_enforcement(test_client, monkeypatch, sample_merged_payload):
    """Test webhook endpoint rejects invalid signatures when GITHUB_WEBHOOK_SECRET is set."""
    secret = "my-webhook-secret"
    monkeypatch.setattr("app.config.settings.GITHUB_WEBHOOK_SECRET", secret)

    payload_bytes = json.dumps(sample_merged_payload).encode("utf-8")

    # 1. Missing header -> 401
    resp = test_client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={"Content-Type": "application/json", "X-GitHub-Delivery": "test-sig-1"},
    )
    assert resp.status_code == 401
    assert "Missing X-Hub-Signature-256" in resp.json()["detail"]

    # 2. Invalid signature -> 401
    resp = test_client.post(
        "/webhook/github",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": "test-sig-2",
            "X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb",
        },
    )
    assert resp.status_code == 401
    assert "Invalid webhook HMAC signature" in resp.json()["detail"]

    # 3. Valid signature -> passes verification
    valid_sig = f"sha256={hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()}"
    with patch.object(pipeline_service, "process_merged_pr", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = {"status": "success", "delivery_id": "test-sig-3"}
        resp = test_client.post(
            "/webhook/github",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Delivery": "test-sig-3",
                "X-Hub-Signature-256": valid_sig,
            },
        )
        assert resp.status_code == 200
        mock_process.assert_awaited_once()


def test_malformed_json_payload(test_client):
    """Test that malformed JSON payloads return 400 Bad Request safely."""
    resp = test_client.post(
        "/webhook/github",
        content=b"{not valid json",
        headers={"Content-Type": "application/json", "X-GitHub-Delivery": "bad-json"},
    )
    assert resp.status_code == 400
    assert "Malformed JSON payload" in resp.json()["detail"]


def test_ping_event_handled(test_client):
    """Test that GitHub ping events receive HTTP 200 pong."""
    resp = test_client.post(
        "/webhook/github",
        json={"zen": "Non-blocking is better than blocking."},
        headers={"X-GitHub-Event": "ping", "X-GitHub-Delivery": "ping-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "pong"


def test_non_pr_event_ignored(test_client):
    """Test that non-pull-request events return HTTP 200 and are ignored."""
    with patch.object(pipeline_service, "process_merged_pr", new_callable=AsyncMock) as mock_process:
        resp = test_client.post(
            "/webhook/github",
            json={"action": "created", "issue": {"number": 1}},
            headers={"X-GitHub-Event": "issues", "X-GitHub-Delivery": "issue-event-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert "only 'pull_request' is handled" in data["reason"]
        mock_process.assert_not_called()


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened", "edited"])
def test_unmerged_pr_actions_ignored(test_client, action):
    """Test that PR actions other than closed-merged return 200 and never invoke downstream pipeline."""
    payload = {
        "action": action,
        "number": 55,
        "pull_request": {
            "number": 55,
            "title": "work in progress",
            "state": "open",
            "merged": False,
        },
        "repository": {"name": "repo", "full_name": "org/repo"},
    }

    with patch.object(pipeline_service, "process_merged_pr", new_callable=AsyncMock) as mock_process, \
         patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate, \
         patch.object(pipeline_service.reflection_chain, "generate_reflection", new_callable=AsyncMock) as mock_chain, \
         patch.object(pipeline_service.email_dispatcher, "send_reflection_email", new_callable=AsyncMock) as mock_email:

        resp = test_client.post(
            "/webhook/github",
            json=payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": f"act-{action}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert "ignored" in data["reason"]

        # Ensure downstream pipeline was NEVER invoked
        mock_process.assert_not_called()
        mock_hydrate.assert_not_called()
        mock_chain.assert_not_called()
        mock_email.assert_not_called()


def test_closed_unmerged_pr_ignored(test_client):
    """Test that a closed PR with merged=False is ignored without invoking pipeline."""
    payload = {
        "action": "closed",
        "number": 60,
        "pull_request": {
            "number": 60,
            "title": "rejected PR",
            "state": "closed",
            "merged": False,
        },
        "repository": {"name": "repo", "full_name": "org/repo"},
    }

    with patch.object(pipeline_service, "process_merged_pr", new_callable=AsyncMock) as mock_process, \
         patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate:

        resp = test_client.post(
            "/webhook/github",
            json=payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "closed-unmerged-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert "closed without being merged" in data["reason"]
        mock_process.assert_not_called()
        mock_hydrate.assert_not_called()


def test_merged_pr_invokes_pipeline_sync(test_client, sample_merged_payload, sample_hydrated_context, sample_reflection_output):
    """Test that a closed and merged PR in sync mode returns the complete reflection result."""
    with patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate, \
         patch.object(pipeline_service.reflection_chain, "generate_reflection", new_callable=AsyncMock) as mock_chain, \
         patch.object(pipeline_service.email_dispatcher, "send_reflection_email", new_callable=AsyncMock) as mock_email:

        mock_hydrate.return_value = sample_hydrated_context
        mock_chain.return_value = sample_reflection_output
        mock_email.return_value = None

        resp = test_client.post(
            "/webhook/github?sync=true",
            json=sample_merged_payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "valid-merged-sync-1"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["pr_number"] == 101
        assert data["repo"] == "acme/backend"
        assert len(data["reflection"]["key_learnings"]) == 3

        mock_hydrate.assert_awaited_once()
        mock_chain.assert_awaited_once()
        mock_email.assert_awaited_once()


def test_merged_pr_timely_acknowledgment_and_delivery_status(test_client, sample_merged_payload, sample_hydrated_context, sample_reflection_output):
    """Test that default webhook returns timely HTTP acknowledgment and processes in background."""
    with patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate, \
         patch.object(pipeline_service.reflection_chain, "generate_reflection", new_callable=AsyncMock) as mock_chain, \
         patch.object(pipeline_service.email_dispatcher, "send_reflection_email", new_callable=AsyncMock) as mock_email:

        mock_hydrate.return_value = sample_hydrated_context
        mock_chain.return_value = sample_reflection_output
        mock_email.return_value = None

        delivery_id = "valid-merged-async-1"
        resp = test_client.post(
            "/webhook/github",
            json=sample_merged_payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": delivery_id},
        )

        # Immediate timely response
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["delivery_id"] == delivery_id

        # Starlette TestClient runs background tasks before post() returns
        mock_hydrate.assert_awaited_once()
        mock_chain.assert_awaited_once()
        mock_email.assert_awaited_once()

        # Query delivery status endpoint
        st_resp = test_client.get(f"/webhook/delivery/{delivery_id}")
        assert st_resp.status_code == 200
        st_data = st_resp.json()
        assert st_data["status"] == "COMPLETED"
        assert st_data["delivery_id"] == delivery_id


def test_pipeline_failure_during_hydration_marks_failed(test_client, sample_merged_payload):
    """Test that failure in GitHub context hydration marks delivery FAILED and stops the pipeline."""
    with patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate, \
         patch.object(pipeline_service.reflection_chain, "generate_reflection", new_callable=AsyncMock) as mock_chain, \
         patch.object(pipeline_service.email_dispatcher, "send_reflection_email", new_callable=AsyncMock) as mock_email:

        mock_hydrate.side_effect = RuntimeError("GitHub API rate limit exceeded")

        deliv_id = "fail-stage-1-hydration"
        resp = test_client.post(
            "/webhook/github?sync=true",
            json=sample_merged_payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": deliv_id},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert "GitHub API rate limit exceeded" in data["error"]

        mock_chain.assert_not_called()
        mock_email.assert_not_called()

        # Check DB status
        st_resp = test_client.get(f"/webhook/delivery/{deliv_id}")
        assert st_resp.status_code == 200
        assert st_resp.json()["status"] == "FAILED"
        assert "GitHub API rate limit exceeded" in st_resp.json()["error_message"]


def test_pipeline_failure_during_gemini_reflection_marks_failed(test_client, sample_merged_payload, sample_hydrated_context):
    """Test that failure in Gemini reflection generation marks delivery FAILED and never sends email."""
    with patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate, \
         patch.object(pipeline_service.reflection_chain, "generate_reflection", new_callable=AsyncMock) as mock_chain, \
         patch.object(pipeline_service.email_dispatcher, "send_reflection_email", new_callable=AsyncMock) as mock_email:

        mock_hydrate.return_value = sample_hydrated_context
        mock_chain.side_effect = ValueError("Gemini returned invalid non-JSON output")

        deliv_id = "fail-stage-2-gemini"
        resp = test_client.post(
            "/webhook/github?sync=true",
            json=sample_merged_payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": deliv_id},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert "invalid non-JSON" in data["error"]

        mock_email.assert_not_called()

        st_resp = test_client.get(f"/webhook/delivery/{deliv_id}")
        assert st_resp.status_code == 200
        assert st_resp.json()["status"] == "FAILED"


def test_pipeline_failure_during_email_dispatch_records_failed_status(test_client, sample_merged_payload, sample_hydrated_context, sample_reflection_output):
    """Test that failure during SMTP email dispatch marks delivery FAILED and records email failure."""
    with patch.object(pipeline_service.github, "hydrate_pr", new_callable=AsyncMock) as mock_hydrate, \
         patch.object(pipeline_service.reflection_chain, "generate_reflection", new_callable=AsyncMock) as mock_chain, \
         patch.object(pipeline_service.email_dispatcher, "send_reflection_email", new_callable=AsyncMock) as mock_email:

        mock_hydrate.return_value = sample_hydrated_context
        mock_chain.return_value = sample_reflection_output
        mock_email.side_effect = ConnectionRefusedError("SMTP server connection refused")

        deliv_id = "fail-stage-3-smtp"
        resp = test_client.post(
            "/webhook/github?sync=true",
            json=sample_merged_payload,
            headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": deliv_id},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert "SMTP server connection refused" in data["error"]

        # Ensure delivery in DB is FAILED
        st_resp = test_client.get(f"/webhook/delivery/{deliv_id}")
        assert st_resp.status_code == 200
        assert st_resp.json()["status"] == "FAILED"


