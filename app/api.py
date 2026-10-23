import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import DatabaseManager, mask_email
from app.logging_config import logger
from app.models import (
    OutreachDraftRequest,
    OutreachDraftResponse,
    OutreachSendRequest,
    PaginatedResponse,
)
from app.webhook import pipeline_service

router = APIRouter(prefix="/api", tags=["PR Chronicler API"])


def get_db() -> DatabaseManager:
    """Dependency provider for database manager."""
    return pipeline_service.db


# =========================================================================
# 1. Overview Dashboard Summary
# =========================================================================

@router.get("/dashboard/summary")
async def get_dashboard_summary(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    """Provides consolidated metrics and health summary for the overview dashboard."""
    summary = await db.get_dashboard_summary()

    # System status breakdown (strictly no secrets exposed)
    effective_model = pipeline_service.reflection_chain.model_name
    system_status = {
        "status": "healthy",
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_effective_model": effective_model,
        "gemini_configured": bool(settings.GOOGLE_API_KEY),
        "github_token_configured": bool(settings.GITHUB_TOKEN),
        "smtp_configured": bool(settings.SMTP_EMAIL and settings.SMTP_APP_PASSWORD and settings.RECIPIENT_EMAIL),
        "webhook_secret_enforced": bool(settings.GITHUB_WEBHOOK_SECRET),
        "database": settings.DATABASE_PATH,
    }
    summary["system_status"] = system_status
    return summary


# =========================================================================
# 2. Pull Requests Endpoints
# =========================================================================

@router.get("/pull-requests", response_model=PaginatedResponse)
async def list_pull_requests(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by repo, title, author, or PR number"),
    status: Optional[str] = Query(None, description="Filter by status (COMPLETED, FAILED, PROCESSING, IGNORED)"),
    repo: Optional[str] = Query(None, description="Filter by repository name"),
    sort_by: str = Query("created_at", description="Sort field (created_at, updated_at, pr_number)"),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse:
    """Lists pull requests with pagination, search, status filters, and sorting."""
    return await db.get_pull_requests(
        page=page,
        limit=limit,
        search=search,
        status=status,
        repo=repo,
        sort_by=sort_by,
        order=order,
    )


@router.get("/pull-requests/{delivery_id}")
async def get_pull_request_detail(
    delivery_id: str,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves full details of a specific pull request, including parsed reflection and email logs."""
    pr_detail = await db.get_pull_request_detail(delivery_id)
    if not pr_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request delivery record '{delivery_id}' not found",
        )
    return pr_detail


# =========================================================================
# 3. Learnings Endpoints
# =========================================================================

@router.get("/learnings", response_model=PaginatedResponse)
async def list_learnings(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search across learnings, repo, or title"),
    repo: Optional[str] = Query(None, description="Filter by repository name"),
    pr_number: Optional[int] = Query(None, description="Filter by PR number"),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse:
    """Lists extracted key engineering takeaways with evidence grounding metadata."""
    return await db.get_learnings(
        page=page,
        limit=limit,
        search=search,
        repo=repo,
        pr_number=pr_number,
    )


# =========================================================================
# 4. Webhook Events Endpoints
# =========================================================================

@router.get("/webhook-events", response_model=PaginatedResponse)
async def list_webhook_events(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (COMPLETED, FAILED, PROCESSING, IGNORED)"),
    search: Optional[str] = Query(None, description="Search by delivery_id, repo, or reason"),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse:
    """Audit log of incoming webhook events with idempotency and processing states."""
    return await db.get_webhook_events(
        page=page,
        limit=limit,
        status=status,
        search=search,
    )


@router.get("/webhook-events/{delivery_id}")
async def get_webhook_event_detail(
    delivery_id: str,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves full detail of a specific webhook event."""
    record = await db.get_delivery(delivery_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook event '{delivery_id}' not found",
        )
    return record.model_dump()


# =========================================================================
# 5. Email Deliveries Endpoints
# =========================================================================

@router.get("/email-deliveries", response_model=PaginatedResponse)
async def list_email_deliveries(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (SENT, FAILED)"),
    search: Optional[str] = Query(None, description="Search by repo, subject, or delivery_id"),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse:
    """Audit log of actual persisted email delivery records with privacy-masked recipients."""
    return await db.get_email_deliveries(
        page=page,
        limit=limit,
        status=status,
        search=search,
    )


# =========================================================================
# 6. System Health & Diagnostics
# =========================================================================

@router.get("/system/health")
async def get_system_health(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    """Comprehensive, non-leaking diagnostic health check for all subsystems."""
    summary = await db.get_dashboard_summary()

    # Database connectivity check
    db_connected = True
    wal_enabled = True
    try:
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            async with conn.execute("PRAGMA journal_mode;") as cursor:
                row = await cursor.fetchone()
                wal_enabled = (row[0].lower() == "wal") if row else False
    except Exception as exc:
        logger.error("DB Health check failed: %s", exc)
        db_connected = False
        wal_enabled = False

    effective_model = pipeline_service.reflection_chain.model_name
    return {
        "status": "healthy" if db_connected else "degraded",
        "service": "PR Chronicler",
        "version": "1.0.0",
        "database": {
            "path": settings.DATABASE_PATH,
            "connected": db_connected,
            "wal_mode": wal_enabled,
            "total_deliveries": summary["total_deliveries"],
        },
        "gemini": {
            "configured": bool(settings.GOOGLE_API_KEY),
            "model": settings.GEMINI_MODEL,
            "effective_model": effective_model,
            "temperature": settings.GEMINI_TEMPERATURE,
        },
        "github": {
            "token_configured": bool(settings.GITHUB_TOKEN),
        },
        "smtp": {
            "configured": bool(settings.SMTP_EMAIL and settings.SMTP_APP_PASSWORD and settings.RECIPIENT_EMAIL),
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "use_tls": settings.SMTP_USE_TLS,
            "recipient_configured": bool(settings.RECIPIENT_EMAIL),
        },
        "webhook_security": {
            "secret_enforced": bool(settings.GITHUB_WEBHOOK_SECRET),
        },
        "last_successful_processing_at": summary["last_successful_processing_at"],
        "counts": {
            "completed": summary["completed_jobs"],
            "failed": summary["failed_jobs"],
            "ignored": summary["ignored_jobs"],
            "learnings": summary["total_learnings"],
            "emails_sent": summary["total_emails_sent"],
        },
    }


# =========================================================================
# 7. Safe Non-Sensitive Settings
# =========================================================================

@router.get("/settings")
async def get_settings_view() -> Dict[str, Any]:
    """Safe, read-only view of application configuration (strictly no secrets returned)."""
    return {
        "environment": {
            "host": settings.HOST,
            "port": settings.PORT,
            "database_path": settings.DATABASE_PATH,
            "log_file": settings.LOG_FILE,
            "log_level": settings.LOG_LEVEL,
        },
        "gemini": {
            "model": settings.GEMINI_MODEL,
            "temperature": settings.GEMINI_TEMPERATURE,
            "api_key_configured": bool(settings.GOOGLE_API_KEY),
        },
        "github": {
            "token_configured": bool(settings.GITHUB_TOKEN),
            "webhook_secret_configured": bool(settings.GITHUB_WEBHOOK_SECRET),
        },
        "smtp": {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "use_tls": settings.SMTP_USE_TLS,
            "sender_email_masked": mask_email(settings.SMTP_EMAIL),
            "recipient_email_masked": mask_email(settings.RECIPIENT_EMAIL),
            "app_password_configured": bool(settings.SMTP_APP_PASSWORD),
        },
        "operational_guidance": {
            "config_method": "Configuration is managed via root .env file and environment variables.",
            "secrets_policy": "Secrets are never exposed via API responses or frontend code.",
            "background_workers": (
                "Background processing uses in-process FastAPI BackgroundTasks. "
                "Any process restart marks interrupted deliveries as FAILED on startup via recover_interrupted_deliveries()."
            ),
        },
    }


# =========================================================================
# 8. GitHub Contribution Explorer Endpoints
# =========================================================================

@router.get("/explorer/search")
async def explorer_search(
    q: str = Query(..., min_length=1, description="GitHub username, profile URL, or repository URL"),
    type: Optional[str] = Query(None, description="Forced search type: 'user' or 'repo'"),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Parses search query and records it in recent searches."""
    mode, id1, id2 = pipeline_service.github_client.parse_github_input(q, forced_type=type)
    if not id1:
        raise HTTPException(status_code=400, detail="Invalid GitHub search input.")

    target = f"{id1}/{id2}" if mode == "repo" and id2 else id1
    await db.record_search(query=q, search_type=mode, target=target)

    return {
        "query": q,
        "mode": mode,
        "identifier1": id1,
        "identifier2": id2,
        "target": target,
    }


@router.get("/explorer/recent-searches")
async def get_recent_searches(
    limit: int = Query(10, ge=1, le=50),
    db: DatabaseManager = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns recent search history for the explorer."""
    return await db.get_recent_searches(limit=limit)


@router.get("/explorer/user/{username}")
async def get_user_profile(
    username: str,
) -> Dict[str, Any]:
    """Fetches public profile metadata for a GitHub user."""
    profile = await pipeline_service.github_client.get_user_profile(username)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"GitHub user '{username}' was not found or is inaccessible.",
        )
    return profile


@router.get("/explorer/user/{username}/repos")
async def get_user_repositories(
    username: str,
    sort: str = Query("updated", description="Sort order: updated, stars, pushed, full_name"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Fetches public repositories for a GitHub user."""
    return await pipeline_service.github_client.get_user_repos(
        username=username, sort=sort, per_page=limit, page=page
    )


@router.get("/explorer/user/{username}/prs")
async def get_user_prs(
    username: str,
    state: Optional[str] = Query(None, description="State filter: 'all', 'merged', 'open', 'closed'"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Fetches pull requests authored by a GitHub user, with analysis status."""
    prs_result = await pipeline_service.github_client.get_user_pull_requests(
        username=username, state=state, page=page, per_page=limit
    )

    # Annotate items with cached analysis / saved indicators if present in DB
    enriched_items = []
    for item in prs_result.get("items", []):
        # Extract repo name from repository_url
        repo_url = item.get("repository_url", "")
        repo_name = "/".join(repo_url.split("/")[-2:]) if repo_url else ""
        pr_number = item.get("number", 0)

        is_analyzed = False
        is_saved = False
        if repo_name and pr_number:
            contrib = await db.get_contribution(repo_name, pr_number)
            if contrib:
                is_analyzed = bool(contrib.get("reflection_json"))
                is_saved = bool(contrib.get("is_saved"))

        item["repo_full_name"] = repo_name
        item["is_analyzed"] = is_analyzed
        item["is_saved"] = is_saved
        enriched_items.append(item)

    prs_result["items"] = enriched_items
    return prs_result


@router.get("/explorer/repo/{owner}/{repo}")
async def get_repo_metadata(
    owner: str,
    repo: str,
) -> Dict[str, Any]:
    """Fetches repository metadata."""
    meta = await pipeline_service.github_client.get_repo_details(owner, repo)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"GitHub repository '{owner}/{repo}' was not found or is inaccessible.",
        )
    return meta


@router.get("/explorer/repo/{owner}/{repo}/prs")
async def get_repo_pull_requests(
    owner: str,
    repo: str,
    state: str = Query("all", description="State filter: 'all', 'open', 'closed'"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    db: DatabaseManager = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Fetches pull requests for a repository."""
    prs = await pipeline_service.github_client.get_repo_pull_requests(
        owner=owner, repo=repo, state=state, page=page, per_page=limit
    )
    repo_name = f"{owner}/{repo}"
    enriched = []
    for pr in prs:
        pr_num = pr.get("number", 0)
        contrib = await db.get_contribution(repo_name, pr_num)
        pr["is_analyzed"] = bool(contrib.get("reflection_json")) if contrib else False
        pr["is_saved"] = bool(contrib.get("is_saved")) if contrib else False
        enriched.append(pr)
    return enriched


@router.get("/explorer/repo/{owner}/{repo}/contributors")
async def get_repo_contributors(
    owner: str,
    repo: str,
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Fetches contributors for a repository."""
    return await pipeline_service.github_client.get_repo_contributors(
        owner=owner, repo=repo, page=page, per_page=limit
    )


@router.get("/explorer/pr/{owner}/{repo}/{pr_number}")
async def get_pr_exploration(
    owner: str,
    repo: str,
    pr_number: int,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Fetches comprehensive PR metadata, changed files, and cached reflection if available."""
    pr_data = await pipeline_service.github_client.get_pr_details(owner, repo, pr_number)
    if not pr_data:
        raise HTTPException(
            status_code=404,
            detail=f"Pull Request #{pr_number} in '{owner}/{repo}' was not found.",
        )

    files, char_count = await pipeline_service.github_client.get_pr_files(
        client=None, owner=owner, repo=repo, pull_number=pr_number
    )

    repo_full = f"{owner}/{repo}"
    cached = await db.get_contribution(repo_full, pr_number)
    reflection = None
    is_saved = False

    if cached:
        is_saved = bool(cached.get("is_saved"))
        if cached.get("reflection_json"):
            try:
                reflection = json.loads(cached["reflection_json"])
            except Exception:
                reflection = None

    # Also check if it was processed via webhook
    if not reflection:
        async with pipeline_service.db._lock:
            pass  # webhook check
        deliveries = await db.get_pull_requests(limit=1, search=f"{repo_full} #{pr_number}")
        if deliveries.items:
            cand = deliveries.items[0]
            if cand.get("reflection_json"):
                try:
                    reflection = json.loads(cand["reflection_json"])
                except Exception:
                    pass

    return {
        "pr": pr_data,
        "files": [f.model_dump() for f in files],
        "total_patch_char_count": char_count,
        "reflection": reflection,
        "is_saved": is_saved,
    }


@router.post("/explorer/pr/{owner}/{repo}/{pr_number}/analyze")
async def analyze_pr_contribution(
    owner: str,
    repo: str,
    pr_number: int,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Generates structured Gemini AI reflection on demand for a PR and caches it."""
    try:
        context = await pipeline_service.github_client.hydrate_pr_by_number(owner, repo, pr_number)
        if not context.title and not context.files:
            raise HTTPException(
                status_code=404,
                detail=f"PR #{pr_number} in '{owner}/{repo}' contains no inspectable files or metadata.",
            )

        reflection = await pipeline_service.reflection_chain.generate_reflection(context)
        reflection_dict = reflection.model_dump()

        repo_full = f"{owner}/{repo}"
        state_str = "merged" if context.merged_at else "closed"

        await db.save_or_update_contribution(
            repo=repo_full,
            pr_number=pr_number,
            pr_title=context.title,
            pr_author=context.author,
            pr_url=context.html_url,
            state=state_str,
            reflection_json=json.dumps(reflection_dict),
            merged_at=context.merged_at,
        )

        return {
            "status": "COMPLETED",
            "repo": repo_full,
            "pr_number": pr_number,
            "reflection": reflection_dict,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to generate AI reflection for %s/%s #%d: %s", owner, repo, pr_number, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI reflection failed: {str(exc)}",
        )


@router.post("/explorer/contributions/save")
async def save_contribution_bookmark(
    payload: Dict[str, Any],
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Bookmarks or un-bookmarks an explored contribution."""
    repo = payload.get("repo")
    pr_number = payload.get("pr_number")
    is_saved = payload.get("is_saved", True)
    if not repo or not pr_number:
        raise HTTPException(status_code=400, detail="Missing repo or pr_number")

    # Ensure contribution row exists
    pr_title = payload.get("pr_title", f"PR #{pr_number}")
    pr_author = payload.get("pr_author", "unknown")
    pr_url = payload.get("pr_url", f"https://github.com/{repo}/pull/{pr_number}")

    await db.save_or_update_contribution(
        repo=repo,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_author=pr_author,
        pr_url=pr_url,
        is_saved=is_saved,
    )
    return {"repo": repo, "pr_number": pr_number, "is_saved": is_saved}


@router.get("/explorer/contributions", response_model=PaginatedResponse)
async def list_explorer_contributions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    repo: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    analyzed_only: bool = Query(False),
    saved_only: bool = Query(False),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse:
    """Lists saved and analyzed contributions from the explorer."""
    return await db.list_contributions(
        page=page,
        limit=limit,
        search=search,
        repo=repo,
        author=author,
        state=state,
        analyzed_only=analyzed_only,
        saved_only=saved_only,
    )


# =========================================================================
# 9. Contributor Email Outreach Endpoints
# =========================================================================

@router.post("/outreach/draft", response_model=OutreachDraftResponse)
async def create_outreach_draft(
    req: OutreachDraftRequest,
) -> OutreachDraftResponse:
    """Generates an initial outreach draft customized for a contributor and specific contribution."""
    repo_mention = f" on {req.repo}" if req.repo else ""
    subject = f"Regarding your open-source work{repo_mention}"

    pr_context_text = ""
    if req.repo and req.pr_number:
        pr_context_text = f"\nI was exploring your contribution to {req.repo} (PR #{req.pr_number}: '{req.pr_title or 'Pull Request'}') and found your technical implementation insightful."

    body = f"""Hi @{req.contributor_username},

I came across your open-source work on GitHub.{pr_context_text}

I'm reaching out because I really appreciate your contributions to the developer community and would love to connect.

Looking forward to hearing from you!

Best regards,
[Your Name]"""

    masked = mask_email(req.recipient_email) if req.recipient_email else None

    return OutreachDraftResponse(
        recipient=req.recipient_email,
        recipient_masked=masked,
        email_source=req.email_source,
        subject=subject,
        body=body,
    )


@router.post("/outreach/send")
async def send_outreach_email(
    req: OutreachSendRequest,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Sends an outreach email with explicit user confirmation and idempotency protection."""
    if not req.confirm_send:
        raise HTTPException(
            status_code=400,
            detail="Explicit user confirmation is required before dispatching an outreach email.",
        )

    if not req.recipient_email or "@" not in req.recipient_email:
        raise HTTPException(
            status_code=400,
            detail="A valid recipient email address is required.",
        )

    # Idempotency check: don't double-send
    existing = await db.get_outreach_by_idempotency_key(req.idempotency_key)
    if existing and existing.get("status") == "SENT":
        return {
            "status": "ALREADY_SENT",
            "message": "This outreach email has already been dispatched.",
            "outreach_id": existing.get("id"),
        }

    try:
        await pipeline_service.email_dispatcher.send_outreach_email(
            recipient=req.recipient_email,
            subject=req.subject,
            body=req.body,
        )

        record = await db.record_outreach(
            recipient_email=req.recipient_email,
            recipient_name=req.contributor_username,
            contributor_username=req.contributor_username,
            repo=req.repo,
            pr_number=req.pr_number,
            subject=req.subject,
            body=req.body,
            status="SENT",
            email_source=req.email_source,
            idempotency_key=req.idempotency_key,
        )

        return {
            "status": "SENT",
            "message": "Outreach email dispatched successfully.",
            "outreach_id": record.get("id"),
        }
    except Exception as exc:
        logger.error("Outreach email dispatch failed: %s", exc)
        await db.record_outreach(
            recipient_email=req.recipient_email,
            recipient_name=req.contributor_username,
            contributor_username=req.contributor_username,
            repo=req.repo,
            pr_number=req.pr_number,
            subject=req.subject,
            body=req.body,
            status="FAILED",
            email_source=req.email_source,
            idempotency_key=req.idempotency_key,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail=f"SMTP dispatch failed: {str(exc)}",
        )


@router.get("/outreach/history", response_model=PaginatedResponse)
async def list_outreach_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: DatabaseManager = Depends(get_db),
) -> PaginatedResponse:
    """Lists outreach email dispatch history with masked recipient email addresses."""
    return await db.list_outreach(page=page, limit=limit, status=status, search=search)

