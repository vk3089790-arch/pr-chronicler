"""Tests for PR Chronicler REST API endpoints, pagination, filtering, and security."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import DatabaseManager, mask_email
from app.main import app
from app.webhook import pipeline_service


@pytest_asyncio.fixture
async def api_client(temp_db, monkeypatch):
    """Provides an authenticated AsyncClient using an isolated temporary test database."""
    # Monkeypatch pipeline_service.db to use temp_db
    monkeypatch.setattr(pipeline_service, "db", temp_db)

    # Seed some sample data in temp_db
    # 1. COMPLETED delivery
    deliv_1 = "deliv-test-completed"
    await temp_db.register_delivery(
        delivery_id=deliv_1,
        repo="acme/api",
        pr_number=101,
        action="closed",
        pr_title="feat: add OAuth2 token authentication",
        pr_author="alice",
        pr_url="https://github.com/acme/api/pull/101",
    )
    reflection_json = """{
        "issue_details": "[Verified] Issue #55 documented missing bearer token support.",
        "execution_summary": "[Verified] Implemented OAuth2 password bearer flow in auth/oauth.py.",
        "key_learnings": [
            "[Verified] Always validate cryptographic token signatures before checking database roles.",
            "[Verified] Centralizing authentication middleware avoids per-route token parsing drift.",
            "[Inferred] Adding automatic token refresh improves client session resiliency."
        ]
    }"""
    await temp_db.mark_completed(
        deliv_1,
        reflection_json,
        pr_title="feat: add OAuth2 token authentication",
        pr_author="alice",
        pr_url="https://github.com/acme/api/pull/101",
    )
    await temp_db.record_email_delivery(
        delivery_id=deliv_1,
        repo="acme/api",
        pr_number=101,
        recipient="team@example.com",
        subject="[OS-Log] PR Merged: acme/api (#101)",
        status="SENT",
    )

    # 2. FAILED delivery
    deliv_2 = "deliv-test-failed"
    await temp_db.register_delivery(
        delivery_id=deliv_2,
        repo="acme/worker",
        pr_number=42,
        action="closed",
        pr_title="fix: database connection pool deadlock",
        pr_author="bob",
        pr_url="https://github.com/acme/worker/pull/42",
    )
    await temp_db.mark_failed(deliv_2, "ResourceExhausted: Gemini quota exceeded")

    # 3. IGNORED delivery
    deliv_3 = "deliv-test-ignored"
    await temp_db.record_ignored(
        delivery_id=deliv_3,
        repo="acme/frontend",
        pr_number=15,
        action="opened",
        reason="Action 'opened' is ignored (only closed and merged PRs are processed)",
        pr_title="docs: update README",
        pr_author="carol",
        pr_url="https://github.com/acme/frontend/pull/15",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_dashboard_summary_endpoint(api_client):
    """Test GET /api/dashboard/summary aggregates true metrics."""
    response = await api_client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    assert data["total_deliveries"] == 3
    assert data["completed_jobs"] == 1
    assert data["failed_jobs"] == 1
    assert data["ignored_jobs"] == 1
    assert data["total_learnings"] == 3
    assert data["total_emails_sent"] == 1
    assert "system_status" in data
    assert data["system_status"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_pull_requests_list_and_filter(api_client):
    """Test GET /api/pull-requests with pagination and filtering."""
    # List all
    res = await api_client.get("/api/pull-requests")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Filter by status
    res_completed = await api_client.get("/api/pull-requests?status=COMPLETED")
    assert res_completed.status_code == 200
    data_completed = res_completed.json()
    assert data_completed["total"] == 1
    assert data_completed["items"][0]["status"] == "COMPLETED"
    assert data_completed["items"][0]["learnings_count"] == 3
    assert data_completed["items"][0]["email_status"] == "SENT"

    # Search query
    res_search = await api_client.get("/api/pull-requests?search=OAuth2")
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert data_search["total"] == 1
    assert data_search["items"][0]["pr_number"] == 101


@pytest.mark.asyncio
async def test_pull_request_detail_and_404(api_client):
    """Test GET /api/pull-requests/{id} for found and non-existent IDs."""
    # Found
    res = await api_client.get("/api/pull-requests/deliv-test-completed")
    assert res.status_code == 200
    data = res.json()
    assert data["delivery_id"] == "deliv-test-completed"
    assert data["pr_number"] == 101
    assert data["reflection"] is not None
    assert len(data["reflection"]["key_learnings"]) == 3
    assert len(data["emails"]) == 1
    assert "team@example.com" not in data["emails"][0]["recipient"]  # Must be masked
    assert "@example.com" in data["emails"][0]["recipient"]

    # 404 Not Found
    res_404 = await api_client.get("/api/pull-requests/deliv-unknown-999")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()


@pytest.mark.asyncio
async def test_learnings_endpoint_extraction_and_evidence(api_client):
    """Test GET /api/learnings extracts takeaways and evidence tags correctly."""
    res = await api_client.get("/api/learnings")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    items = data["items"]
    assert len(items) == 3

    # Check evidence tags
    first_learning = items[0]
    assert "evidence_tags" in first_learning
    assert "pr_url" in first_learning
    assert "repo" in first_learning

    # Search filter
    res_search = await api_client.get("/api/learnings?search=middleware")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1


@pytest.mark.asyncio
async def test_webhook_events_list_and_detail(api_client):
    """Test GET /api/webhook-events audit listing."""
    res = await api_client.get("/api/webhook-events")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3

    # Detail
    res_det = await api_client.get("/api/webhook-events/deliv-test-failed")
    assert res_det.status_code == 200
    assert res_det.json()["status"] == "FAILED"
    assert "ResourceExhausted" in res_det.json()["error_message"]


@pytest.mark.asyncio
async def test_email_deliveries_privacy_and_list(api_client):
    """Test GET /api/email-deliveries protects recipient privacy."""
    res = await api_client.get("/api/email-deliveries")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["status"] == "SENT"
    assert "team@example.com" not in item["recipient"]
    assert "t***m@example.com" == item["recipient"]


@pytest.mark.asyncio
async def test_system_health_and_settings_never_leak_secrets(api_client):
    """Verify that system health and settings endpoints NEVER expose private credentials."""
    # Health endpoint
    res_health = await api_client.get("/api/system/health")
    assert res_health.status_code == 200
    health_text = res_health.text
    assert "GOOGLE_API_KEY" not in health_text
    assert "SMTP_APP_PASSWORD" not in health_text
    assert "GITHUB_TOKEN" not in health_text
    assert "GITHUB_WEBHOOK_SECRET" not in health_text

    # Settings endpoint
    res_settings = await api_client.get("/api/settings")
    assert res_settings.status_code == 200
    settings_text = res_settings.text
    assert "GOOGLE_API_KEY" not in settings_text
    assert "SMTP_APP_PASSWORD" not in settings_text
    assert "GITHUB_TOKEN" not in settings_text
    assert "GITHUB_WEBHOOK_SECRET" not in settings_text
    assert res_settings.json()["smtp"]["sender_email_masked"] is not None


def test_mask_email_utility():
    """Test email masking edge cases."""
    assert mask_email("vk3089790@gmail.com") == "v***0@gmail.com"
    assert mask_email("ab@gmail.com") == "a***@gmail.com"
    assert mask_email("a@b.com") == "a***@b.com"
    assert mask_email("") == "Not configured"
    assert mask_email(None) == "Not configured"


@pytest.mark.asyncio
async def test_empty_database_endpoints(tmp_path, monkeypatch):
    """Test all read endpoints return clean empty responses when the database has zero records."""
    empty_db = DatabaseManager(str(tmp_path / "empty.db"))
    await empty_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", empty_db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Summary
        res_sum = await client.get("/api/dashboard/summary")
        assert res_sum.status_code == 200
        sum_data = res_sum.json()
        assert sum_data["total_prs"] == 0
        assert sum_data["total_deliveries"] == 0
        assert sum_data["completed_jobs"] == 0
        assert sum_data["total_learnings"] == 0
        assert sum_data["recent_activity"] == []

        # 2. Pull requests
        res_prs = await client.get("/api/pull-requests")
        assert res_prs.status_code == 200
        assert res_prs.json()["items"] == []
        assert res_prs.json()["total"] == 0

        # 3. Learnings
        res_learnings = await client.get("/api/learnings")
        assert res_learnings.status_code == 200
        assert res_learnings.json()["items"] == []
        assert res_learnings.json()["total"] == 0

        # 4. Webhook events
        res_events = await client.get("/api/webhook-events")
        assert res_events.status_code == 200
        assert res_events.json()["items"] == []
        assert res_events.json()["total"] == 0

        # 5. Email deliveries
        res_emails = await client.get("/api/email-deliveries")
        assert res_emails.status_code == 200
        assert res_emails.json()["items"] == []
        assert res_emails.json()["total"] == 0


@pytest.mark.asyncio
async def test_pagination_boundary_validation(api_client):
    """Test validation boundaries on pagination parameters."""
    # page < 1 should return 422
    res_bad_page = await api_client.get("/api/pull-requests?page=0")
    assert res_bad_page.status_code == 422

    # limit > 100 should return 422
    res_bad_limit = await api_client.get("/api/pull-requests?limit=101")
    assert res_bad_limit.status_code == 422

    # limit < 1 should return 422
    res_zero_limit = await api_client.get("/api/pull-requests?limit=0")
    assert res_zero_limit.status_code == 422


@pytest.mark.asyncio
async def test_pull_requests_sorting_order(api_client):
    """Test sorting pull requests by pr_number in asc vs desc order."""
    res_asc = await api_client.get("/api/pull-requests?sort_by=pr_number&order=asc")
    assert res_asc.status_code == 200
    prs_asc = [item["pr_number"] for item in res_asc.json()["items"]]
    assert prs_asc == sorted(prs_asc)

    res_desc = await api_client.get("/api/pull-requests?sort_by=pr_number&order=desc")
    assert res_desc.status_code == 200
    prs_desc = [item["pr_number"] for item in res_desc.json()["items"]]
    assert prs_desc == sorted(prs_desc, reverse=True)


@pytest.mark.asyncio
async def test_read_endpoints_never_trigger_external_side_effects(api_client, mocker):
    """Verify that read endpoints and dashboard refreshes never trigger emails, LLMs, or GitHub API."""
    mock_email = mocker.patch.object(pipeline_service.email_dispatcher, "send_reflection_email")
    mock_gemini = mocker.patch.object(pipeline_service.reflection_chain, "generate_reflection")
    mock_github = mocker.patch.object(pipeline_service.github, "hydrate_pr")

    endpoints = [
        "/api/dashboard/summary",
        "/api/pull-requests",
        "/api/pull-requests/deliv-test-completed",
        "/api/learnings",
        "/api/webhook-events",
        "/api/email-deliveries",
        "/api/system/health",
        "/api/settings",
    ]

    for ep in endpoints:
        res = await api_client.get(ep)
        assert res.status_code in (200, 404)

    # Ensure zero external calls occurred
    assert mock_email.call_count == 0
    assert mock_gemini.call_count == 0
    assert mock_github.call_count == 0

