"""Shared pytest fixtures for PR Chronicler tests."""

import os
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.config import Settings
from app.database import DatabaseManager
from app.models import (
    ChangedFile,
    GitHubPullRequest,
    GitHubRepo,
    GitHubUser,
    GitHubWebhookPayload,
    HydratedPRContext,
    LinkedIssue,
    ReflectionOutput,
)


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """Provides test settings pointing to a temporary SQLite database."""
    test_db = str(tmp_path / "test_chronicler.db")
    monkeypatch.setattr("app.config.settings.DATABASE_PATH", test_db)
    monkeypatch.setattr("app.config.settings.GOOGLE_API_KEY", "mock-test-google-key")
    monkeypatch.setattr("app.config.settings.GITHUB_TOKEN", "mock-test-github-token")
    monkeypatch.setattr("app.config.settings.GITHUB_WEBHOOK_SECRET", "")
    monkeypatch.setattr("app.config.settings.SMTP_EMAIL", "bot@example.com")
    monkeypatch.setattr("app.config.settings.SMTP_APP_PASSWORD", "secret-app-password")
    monkeypatch.setattr("app.config.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.config.settings.SMTP_PORT", 587)
    monkeypatch.setattr("app.config.settings.RECIPIENT_EMAIL", "devs@example.com")
    return test_db


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    """Creates and initializes an isolated SQLite database."""
    db_path = str(tmp_path / "idempotency_test.db")
    db = DatabaseManager(db_path)
    await db.init_db()
    return db


@pytest.fixture
def sample_merged_payload():
    """Sample GitHub webhook payload for a merged pull request."""
    return {
        "action": "closed",
        "number": 101,
        "pull_request": {
            "id": 500101,
            "number": 101,
            "title": "fix: resolve deadlock in connection pool worker",
            "body": "Replaces blocking lock with timeout guard.\n\nFixes #42\nResolves #45",
            "state": "closed",
            "merged": True,
            "merged_at": "2026-10-22T08:00:00Z",
            "merge_commit_sha": "def456abc123",
            "html_url": "https://github.com/acme/backend/pull/101",
            "user": {"login": "dev-alice", "id": 123},
        },
        "repository": {
            "name": "backend",
            "full_name": "acme/backend",
            "owner": {"login": "acme"},
        },
        "sender": {"login": "dev-alice"},
    }


@pytest.fixture
def sample_hydrated_context():
    """Sample hydrated PR context."""
    return HydratedPRContext(
        repo_owner="acme",
        repo_name="backend",
        pr_number=101,
        title="fix: resolve deadlock in connection pool worker",
        author="dev-alice",
        body="Replaces blocking lock with timeout guard.\n\nFixes #42",
        html_url="https://github.com/acme/backend/pull/101",
        merged_at="2026-10-22T08:00:00Z",
        merge_commit_sha="def456abc123",
        files=[
            ChangedFile(
                filename="pool/worker.py",
                status="modified",
                additions=15,
                deletions=4,
                changes=19,
                patch="@@ -10,4 +10,15 @@\n- lock.acquire()\n+ if not lock.acquire(timeout=5.0):\n+     raise PoolTimeoutError()",
            ),
            ChangedFile(
                filename="tests/test_worker.py",
                status="added",
                additions=30,
                deletions=0,
                changes=30,
                patch="@@ -0,0 +1,30 @@\n+def test_pool_timeout():\n+    assert True",
            ),
        ],
        linked_issues=[
            LinkedIssue(
                number=42,
                title="Worker deadlocks when database connection hangs",
                body="Under heavy load, connection pool worker hangs indefinitely.",
                state="closed",
                html_url="https://github.com/acme/backend/issues/42",
            )
        ],
        total_patch_char_count=185,
    )


@pytest.fixture
def sample_reflection_output():
    """Sample valid ReflectionOutput."""
    return ReflectionOutput(
        issue_details="Issue #42 documented an indefinite hang in the connection pool worker under high contention when DB connections stalled.",
        execution_summary="Modified pool/worker.py to replace unconstrained lock acquisition with a 5.0 second timeout and added comprehensive test coverage in tests/test_worker.py.",
        key_learnings=[
            "Always enforce bounded timeouts on thread synchronization primitives in I/O worker pools.",
            "Distinguish network-level timeouts from internal lock acquisition contention.",
            "Adding isolated timeout regression tests prevents concurrency regressions under CI load.",
        ],
    )
