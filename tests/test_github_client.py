"""Tests for GitHub REST API client hydration, pagination, and linked issue extraction."""

import httpx
import pytest
import respx

from app.github_client import GitHubClient
from app.models import ChangedFile, HydratedPRContext


def test_extract_linked_issue_numbers():
    """Verify regex extraction of issue numbers with diverse keywords and formats."""
    client = GitHubClient(token="test-token")

    body = """
    This PR addresses multiple tasks:
    - Fixes #12 (deadlock in worker pool)
    - closes #15 and resolves #20
    - Also fixed #12 again (should be deduplicated)
    - Closed https://github.com/acme/backend/issues/99
    - Resolves acme/backend#105
    - Random text with #999 without trigger keyword should not match
    """

    issues = client.extract_linked_issue_numbers(body)
    assert issues == [12, 15, 20, 99, 105]

    # Edge cases
    assert client.extract_linked_issue_numbers(None) == []
    assert client.extract_linked_issue_numbers("") == []
    assert client.extract_linked_issue_numbers("No issue keywords here #123") == []


@pytest.mark.asyncio
async def test_pagination_and_patch_char_count():
    """Verify that multiple pages of files are retrieved and patch characters are summed."""
    client = GitHubClient(token="test-token")

    # Generate 100 items on page 1, and 2 items on page 2
    page1_data = [
        {"filename": f"file_{i}.py", "status": "modified", "additions": 2, "deletions": 1, "patch": f"patch_content_{i}"}
        for i in range(100)
    ]
    page2_data = [
        {"filename": "file_100.py", "status": "added", "additions": 10, "deletions": 0, "patch": "hello_world"},
        {"filename": "binary.png", "status": "added", "additions": 0, "deletions": 0, "patch": None},  # Missing patch
    ]

    with respx.mock(base_url="https://api.github.com") as respx_mock:
        respx_mock.get("/repos/owner/repo/pulls/1/files?per_page=100&page=1").respond(
            status_code=200, json=page1_data
        )
        respx_mock.get("/repos/owner/repo/pulls/1/files?per_page=100&page=2").respond(
            status_code=200, json=page2_data
        )

        async with httpx.AsyncClient() as http_client:
            files, total_chars = await client.get_pr_files(http_client, "owner", "repo", 1)

        assert len(files) == 102
        # Verify page 2 binary file handled gracefully
        assert files[-1].filename == "binary.png"
        assert files[-1].patch is None

        # Total chars should include all patches from page 1 + "hello_world" (11 chars)
        expected_chars = sum(len(f["patch"]) for f in page1_data) + len("hello_world")
        assert total_chars == expected_chars


@pytest.mark.asyncio
async def test_get_issue_details_success():
    """Verify successful retrieval of linked issue title and body."""
    client = GitHubClient(token="test-token")

    with respx.mock(base_url="https://api.github.com") as respx_mock:
        respx_mock.get("/repos/owner/repo/issues/42").respond(
            status_code=200,
            json={
                "number": 42,
                "title": "Fix crash on startup",
                "body": "App crashes if port is already bound.",
                "state": "closed",
                "html_url": "https://github.com/owner/repo/issues/42",
            },
        )

        async with httpx.AsyncClient() as http_client:
            issue = await client.get_issue_details(http_client, "owner", "repo", 42)

        assert issue is not None
        assert issue.number == 42
        assert issue.title == "Fix crash on startup"
        assert issue.body == "App crashes if port is already bound."


@pytest.mark.asyncio
async def test_missing_or_private_issue_handled_gracefully():
    """Verify that a 404 for a missing or private issue does not raise an exception."""
    client = GitHubClient(token="test-token")

    with respx.mock(base_url="https://api.github.com") as respx_mock:
        respx_mock.get("/repos/owner/repo/issues/404").respond(status_code=404)

        async with httpx.AsyncClient() as http_client:
            issue = await client.get_issue_details(http_client, "owner", "repo", 404)

        assert issue is None


@pytest.mark.asyncio
async def test_rate_limit_and_error_handling():
    """Verify graceful handling when GitHub API returns rate limits (403) or timeouts."""
    client = GitHubClient(token="test-token")

    with respx.mock(base_url="https://api.github.com") as respx_mock:
        respx_mock.get("/repos/owner/repo/pulls/2/files?per_page=100&page=1").respond(
            status_code=403,
            headers={"x-ratelimit-remaining": "0"},
            json={"message": "API rate limit exceeded"},
        )

        async with httpx.AsyncClient() as http_client:
            files, total_chars = await client.get_pr_files(http_client, "owner", "repo", 2)

        assert files == []
        assert total_chars == 0


@pytest.mark.asyncio
async def test_full_pr_hydration(sample_merged_payload):
    """Test end-to-end hydration of PR context with files and linked issue."""
    client = GitHubClient(token="ghp_test_token")

    files_mock = [
        {"filename": "app.py", "status": "modified", "additions": 5, "deletions": 2, "patch": "@@ -1,2 +1,5 @@\n+print('hello')"},
    ]
    issue_mock = {
        "number": 42,
        "title": "Bug in app",
        "body": "Crash occurs on line 12",
        "state": "closed",
        "html_url": "https://github.com/acme/backend/issues/42",
    }

    with respx.mock(base_url="https://api.github.com") as respx_mock:
        respx_mock.get("/repos/acme/backend/pulls/101/files?per_page=100&page=1").respond(
            status_code=200, json=files_mock
        )
        respx_mock.get("/repos/acme/backend/issues/42").respond(
            status_code=200, json=issue_mock
        )
        respx_mock.get("/repos/acme/backend/issues/45").respond(
            status_code=404  # Issue 45 not found
        )

        context = await client.hydrate_pr(sample_merged_payload)

        assert context.repo_owner == "acme"
        assert context.repo_name == "backend"
        assert context.pr_number == 101
        assert len(context.files) == 1
        assert context.files[0].filename == "app.py"
        assert len(context.linked_issues) == 1
        assert context.linked_issues[0].number == 42
        assert context.total_patch_char_count == len(files_mock[0]["patch"])


@pytest.mark.asyncio
async def test_github_client_close_and_context_manager():
    """Verify GitHubClient.close() and async context manager run cleanly."""
    gh = GitHubClient()
    # Calling close on default client is a clean no-op
    await gh.close()

    # Async context manager works
    async with GitHubClient() as client:
        assert client is not None

    # External client is closed when close() is called
    external_client = httpx.AsyncClient()
    gh_ext = GitHubClient(client=external_client)
    assert not external_client.is_closed
    await gh_ext.close()
    assert external_client.is_closed

