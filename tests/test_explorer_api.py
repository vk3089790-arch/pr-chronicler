"""Tests for GitHub Contribution Explorer and Contributor Outreach Platform."""

import json
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.database import DatabaseManager, mask_email
from app.github_client import GitHubClient
from app.main import app
from app.models import ChangedFile, HydratedPRContext, ReflectionOutput
from app.webhook import pipeline_service


@pytest.fixture
def test_db(tmp_path):
    """Provides a fresh isolated SQLite database for explorer tests."""
    db_file = str(tmp_path / "test_explorer.db")
    db = DatabaseManager(db_path=db_file)
    return db


@pytest.mark.asyncio
async def test_parse_github_input():
    client = GitHubClient(token="mock-token")
    
    # 1. Plain username
    mode, id1, id2 = client.parse_github_input("octocat")
    assert mode == "user"
    assert id1 == "octocat"
    assert id2 is None

    # 2. Username with @
    mode, id1, id2 = client.parse_github_input("@octocat")
    assert mode == "user"
    assert id1 == "octocat"
    assert id2 is None

    # 3. User profile URL
    mode, id1, id2 = client.parse_github_input("https://github.com/octocat")
    assert mode == "user"
    assert id1 == "octocat"
    assert id2 is None

    # 4. User profile URL with trailing slash
    mode, id1, id2 = client.parse_github_input("https://github.com/octocat/")
    assert mode == "user"
    assert id1 == "octocat"
    assert id2 is None

    # 5. Repo path
    mode, id1, id2 = client.parse_github_input("pallets/flask")
    assert mode == "repo"
    assert id1 == "pallets"
    assert id2 == "flask"

    # 6. Repo URL
    mode, id1, id2 = client.parse_github_input("https://github.com/pallets/flask")
    assert mode == "repo"
    assert id1 == "pallets"
    assert id2 == "flask"

    # 7. Forced type
    mode, id1, id2 = client.parse_github_input("pallets/flask", forced_type="user")
    assert mode == "user"
    assert id1 == "pallets"


@pytest.mark.asyncio
async def test_explorer_search_endpoint(test_db, monkeypatch):
    await test_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", test_db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Search for a user
        res = await ac.get("/api/explorer/search?q=torvalds")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "user"
        assert data["identifier1"] == "torvalds"
        assert data["target"] == "torvalds"

        # Search for a repo URL
        res = await ac.get("/api/explorer/search?q=https://github.com/fastapi/fastapi")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "repo"
        assert data["identifier1"] == "fastapi"
        assert data["identifier2"] == "fastapi"
        assert data["target"] == "fastapi/fastapi"

        # Check recent searches
        res = await ac.get("/api/explorer/recent-searches")
        assert res.status_code == 200
        recent = res.json()
        assert len(recent) == 2
        assert recent[0]["target"] == "fastapi/fastapi"
        assert recent[1]["target"] == "torvalds"


@pytest.mark.asyncio
async def test_user_profile_and_repos_mocked(test_db, monkeypatch):
    await test_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", test_db)

    # Mock github client methods
    async def mock_get_user_profile(username, client=None):
        if username == "octocat":
            return {
                "login": "octocat",
                "id": 583231,
                "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
                "name": "The Octocat",
                "bio": "Building open-source software.",
                "public_repos": 8,
                "followers": 15000,
                "following": 9,
                "email": "octocat@github.com",
            }
        return None

    async def mock_get_user_repos(username, sort="updated", per_page=30, page=1, client=None):
        return [
            {
                "name": "Hello-World",
                "full_name": f"{username}/Hello-World",
                "description": "My first repo",
                "stargazers_count": 2500,
                "language": "Python",
            }
        ]

    monkeypatch.setattr(pipeline_service.github_client, "get_user_profile", mock_get_user_profile)
    monkeypatch.setattr(pipeline_service.github_client, "get_user_repos", mock_get_user_repos)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Success user profile
        res = await ac.get("/api/explorer/user/octocat")
        assert res.status_code == 200
        assert res.json()["login"] == "octocat"
        assert res.json()["name"] == "The Octocat"

        # Non-existent user -> 404
        res = await ac.get("/api/explorer/user/nonexistent_ghost_user")
        assert res.status_code == 404

        # Repositories
        res = await ac.get("/api/explorer/user/octocat/repos")
        assert res.status_code == 200
        repos = res.json()
        assert len(repos) == 1
        assert repos[0]["name"] == "Hello-World"


@pytest.mark.asyncio
async def test_user_prs_and_state_filters(test_db, monkeypatch):
    await test_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", test_db)

    async def mock_get_user_prs(username, state=None, page=1, per_page=30, client=None):
        return {
            "total_count": 1,
            "items": [
                {
                    "number": 42,
                    "title": "Add telemetry and observability",
                    "html_url": "https://github.com/org/repo/pull/42",
                    "repository_url": "https://api.github.com/repos/org/repo",
                    "state": "closed",
                    "created_at": "2026-03-01T12:00:00Z",
                }
            ],
        }

    monkeypatch.setattr(pipeline_service.github_client, "get_user_pull_requests", mock_get_user_prs)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/explorer/user/alice/prs?state=merged")
        assert res.status_code == 200
        data = res.json()
        assert data["total_count"] == 1
        item = data["items"][0]
        assert item["number"] == 42
        assert item["repo_full_name"] == "org/repo"
        assert item["is_analyzed"] is False


@pytest.mark.asyncio
async def test_repo_metadata_and_contributors(test_db, monkeypatch):
    await test_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", test_db)

    async def mock_get_repo_details(owner, repo, client=None):
        if owner == "pallets" and repo == "flask":
            return {
                "name": "flask",
                "full_name": "pallets/flask",
                "description": "The Python micro framework for building web applications.",
                "stargazers_count": 68000,
                "language": "Python",
                "topics": ["python", "web", "framework"],
            }
        return None

    async def mock_get_repo_contributors(owner, repo, page=1, per_page=30, client=None):
        return [
            {
                "login": "mitsuhiko",
                "avatar_url": "https://avatars.githubusercontent.com/u/7396?v=4",
                "contributions": 1200,
            }
        ]

    monkeypatch.setattr(pipeline_service.github_client, "get_repo_details", mock_get_repo_details)
    monkeypatch.setattr(pipeline_service.github_client, "get_repo_contributors", mock_get_repo_contributors)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/explorer/repo/pallets/flask")
        assert res.status_code == 200
        assert res.json()["full_name"] == "pallets/flask"

        res = await ac.get("/api/explorer/repo/pallets/nonexistent")
        assert res.status_code == 404

        res = await ac.get("/api/explorer/repo/pallets/flask/contributors")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["login"] == "mitsuhiko"


@pytest.mark.asyncio
async def test_pr_exploration_and_gemini_analysis(test_db, monkeypatch):
    await test_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", test_db)

    # Mock PR hydration and files
    async def mock_get_pr_details(owner, repo, pull_number, client=None):
        return {
            "number": pull_number,
            "title": "Optimize caching mechanism in route handler",
            "html_url": f"https://github.com/{owner}/{repo}/pull/{pull_number}",
            "user": {"login": "contributor123"},
            "state": "closed",
            "merged_at": "2026-03-05T10:00:00Z",
        }

    async def mock_get_pr_files(client, owner, repo, pull_number):
        files = [
            ChangedFile(
                filename="src/cache.py",
                status="modified",
                additions=15,
                deletions=5,
                changes=20,
                patch="@@ -1,5 +1,15 @@\n+def cache_result(): pass",
            )
        ]
        return files, 35

    async def mock_hydrate_pr_by_number(owner, repo, pull_number, client=None):
        return HydratedPRContext(
            repo_owner=owner,
            repo_name=repo,
            pr_number=pull_number,
            title="Optimize caching mechanism in route handler",
            author="contributor123",
            html_url=f"https://github.com/{owner}/{repo}/pull/{pull_number}",
            merged_at="2026-03-05T10:00:00Z",
            files=[
                ChangedFile(
                    filename="src/cache.py",
                    status="modified",
                    additions=15,
                    deletions=5,
                    changes=20,
                    patch="@@ -1,5 +1,15 @@\n+def cache_result(): pass",
                )
            ],
            total_patch_char_count=35,
        )

    # Mock reflection chain
    mock_reflection = ReflectionOutput(
        issue_details="[Verified] Route handler re-computed results without checking Redis cache.",
        execution_summary="[Verified] Added cache_result decorator in src/cache.py.",
        key_learnings=[
            "1. [Verified] Decorator prevents duplicate executions across requests.",
            "2. [Verified] Fallback handles Redis disconnection without throwing 500 errors.",
            "3. [Inferred] Cache TTL should be carefully tuned to prevent stale data.",
        ],
    )

    async def mock_generate_reflection(context):
        return mock_reflection

    monkeypatch.setattr(pipeline_service.github_client, "get_pr_details", mock_get_pr_details)
    monkeypatch.setattr(pipeline_service.github_client, "get_pr_files", mock_get_pr_files)
    monkeypatch.setattr(pipeline_service.github_client, "hydrate_pr_by_number", mock_hydrate_pr_by_number)
    monkeypatch.setattr(pipeline_service.reflection_chain, "generate_reflection", mock_generate_reflection)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Fetch PR exploration before analysis
        res = await ac.get("/api/explorer/pr/org/repo/99")
        assert res.status_code == 200
        pr_data = res.json()
        assert pr_data["pr"]["number"] == 99
        assert pr_data["reflection"] is None
        assert len(pr_data["files"]) == 1

        # 2. Trigger on-demand AI analysis
        res = await ac.post("/api/explorer/pr/org/repo/99/analyze")
        assert res.status_code == 200
        analysis_data = res.json()
        assert analysis_data["status"] == "COMPLETED"
        assert len(analysis_data["reflection"]["key_learnings"]) == 3

        # 3. Fetch PR exploration again — reflection should now be cached!
        res = await ac.get("/api/explorer/pr/org/repo/99")
        assert res.status_code == 200
        cached_data = res.json()
        assert cached_data["reflection"] is not None
        assert "[Verified] Route handler" in cached_data["reflection"]["issue_details"]

        # 4. Save bookmark
        save_res = await ac.post("/api/explorer/contributions/save", json={"repo": "org/repo", "pr_number": 99, "is_saved": True})
        assert save_res.status_code == 200
        assert save_res.json()["is_saved"] is True

        # 5. List contributions
        list_res = await ac.get("/api/explorer/contributions?saved_only=true")
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 1
        assert list_res.json()["items"][0]["pr_number"] == 99


@pytest.mark.asyncio
async def test_contributor_outreach_workflow(test_db, monkeypatch):
    await test_db.init_db()
    monkeypatch.setattr(pipeline_service, "db", test_db)

    # 1. Draft generation
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        draft_payload = {
            "contributor_username": "octocat",
            "recipient_email": "octocat@github.com",
            "repo": "pallets/flask",
            "pr_number": 1234,
            "pr_title": "Fix memory leak in request teardown",
            "email_source": "public_profile",
        }
        draft_res = await ac.post("/api/outreach/draft", json=draft_payload)
        assert draft_res.status_code == 200
        draft = draft_res.json()
        assert draft["recipient"] == "octocat@github.com"
        assert draft["recipient_masked"] == "o***t@github.com"
        assert "pallets/flask" in draft["subject"]
        assert "@octocat" in draft["body"]
        assert "Fix memory leak" in draft["body"]

        # 2. Send without explicit confirmation -> 400 Bad Request
        send_payload = {
            "recipient_email": "octocat@github.com",
            "subject": draft["subject"],
            "body": draft["body"],
            "contributor_username": "octocat",
            "repo": "pallets/flask",
            "pr_number": 1234,
            "email_source": "public_profile",
            "idempotency_key": "outreach-key-101",
            "confirm_send": False,
        }
        res = await ac.post("/api/outreach/send", json=send_payload)
        assert res.status_code == 400
        assert "confirmation is required" in res.json()["detail"].lower()

        # 3. Send with confirmation and mocked SMTP
        mock_send_outreach = AsyncMock(return_value=None)
        monkeypatch.setattr(pipeline_service.email_dispatcher, "send_outreach_email", mock_send_outreach)

        send_payload["confirm_send"] = True
        res = await ac.post("/api/outreach/send", json=send_payload)
        assert res.status_code == 200
        assert res.json()["status"] == "SENT"
        assert mock_send_outreach.await_count == 1

        # 4. Send again with same idempotency key -> returns ALREADY_SENT, does not re-send
        res_dup = await ac.post("/api/outreach/send", json=send_payload)
        assert res_dup.status_code == 200
        assert res_dup.json()["status"] == "ALREADY_SENT"
        assert mock_send_outreach.await_count == 1  # No second dispatch!

        # 5. Verify outreach history endpoint masks email
        hist_res = await ac.get("/api/outreach/history")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert history["total"] == 1
        item = history["items"][0]
        assert item["recipient_masked"] == "o***t@github.com"
        assert "recipient_email" not in item  # Raw email never exposed!
        assert item["status"] == "SENT"
