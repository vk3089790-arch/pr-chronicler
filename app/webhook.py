"""FastAPI webhook routing and pipeline coordination."""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.config import Settings, settings
from app.database import DatabaseManager
from app.email_dispatcher import EmailDispatcher
from app.github_client import GitHubClient
from app.logging_config import logger
from app.models import GitHubWebhookPayload, ReflectionOutput
from app.reflection_chain import ReflectionChain


def verify_github_signature(secret: str, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """Verifies that the webhook payload matches the HMAC SHA-256 signature."""
    if not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False

    computed = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    expected = f"sha256={computed}"
    return hmac.compare_digest(expected, signature_header)


class WebhookPipeline:
    """Coordinates hydration, LLM reflection, email dispatch, and idempotency tracking."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        github_client: Optional[GitHubClient] = None,
        reflection_chain: Optional[ReflectionChain] = None,
        email_dispatcher: Optional[EmailDispatcher] = None,
    ):
        self.db = db_manager or DatabaseManager(settings.DATABASE_PATH)
        self.github = github_client or GitHubClient()
        self.github_client = self.github
        self.reflection_chain = reflection_chain or ReflectionChain()
        self.email_dispatcher = email_dispatcher or EmailDispatcher()

    async def process_merged_pr(
        self,
        payload: Dict[str, Any],
        delivery_id: str,
    ) -> Dict[str, Any]:
        """Runs the complete hydration, LLM reflection, and SMTP dispatch pipeline."""
        start_time = time.time()
        pr_data = payload.get("pull_request") or {}
        pr_number = pr_data.get("number") or payload.get("number") or 0
        repo_data = payload.get("repository") or {}
        repo_name = repo_data.get("full_name") or repo_data.get("name") or "unknown/unknown"

        try:
            # 1. Hydrate PR Context
            logger.info("Delivery %s: Starting GitHub context hydration for %s #%d", delivery_id, repo_name, pr_number)
            context = await self.github.hydrate_pr(payload)
            logger.info(
                "Delivery %s: Retrieved %d diff characters across %d files for %s #%d",
                delivery_id,
                context.total_patch_char_count,
                len(context.files),
                repo_name,
                pr_number,
            )

            # 2. Generate Structured Technical Reflection via LangChain LCEL
            logger.info("Delivery %s: Generating structured reflection via Gemini LCEL chain", delivery_id)
            reflection = await self.reflection_chain.generate_reflection(context)
            reflection_json = reflection.model_dump_json(indent=2)
            logger.info(
                "Delivery %s: Generated reflection successfully:\n%s",
                delivery_id,
                reflection_json,
            )

            # 3. Dispatch Email via SMTP
            logger.info("Delivery %s: Dispatching reflection email to %s", delivery_id, self.email_dispatcher.recipient_email)
            await self.email_dispatcher.send_reflection_email(context, reflection)
            logger.info("Delivery %s: Email dispatch succeeded", delivery_id)

            # Record email delivery attempt in DB
            subject = self.email_dispatcher.build_subject(repo_name, pr_number)
            await self.db.record_email_delivery(
                delivery_id=delivery_id,
                repo=repo_name,
                pr_number=pr_number,
                recipient=self.email_dispatcher.recipient_email,
                subject=subject,
                status="SENT",
            )

            # 4. Mark DB as COMPLETED with metadata
            await self.db.mark_completed(
                delivery_id,
                reflection_json,
                pr_title=context.title,
                pr_author=context.author,
                pr_url=context.html_url,
            )

            duration = time.time() - start_time
            logger.info("Delivery %s: Completed successfully in %.2f seconds", delivery_id, duration)

            return {
                "status": "success",
                "delivery_id": delivery_id,
                "repo": repo_name,
                "pr_number": pr_number,
                "duration_seconds": round(duration, 3),
                "diff_character_count": context.total_patch_char_count,
                "reflection": reflection.model_dump(),
            }

        except Exception as exc:
            duration = time.time() - start_time
            err_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.error("Delivery %s: Processing failed after %.2f seconds: %s", delivery_id, duration, err_msg, exc_info=True)
            await self.db.mark_failed(delivery_id, err_msg)
            if "smtp" in err_msg.lower() or "mail" in err_msg.lower():
                await self.db.record_email_delivery(
                    delivery_id=delivery_id,
                    repo=repo_name,
                    pr_number=pr_number,
                    recipient=self.email_dispatcher.recipient_email,
                    subject=self.email_dispatcher.build_subject(repo_name, pr_number),
                    status="FAILED",
                    error_message=err_msg,
                )
            return {
                "status": "failed",
                "delivery_id": delivery_id,
                "repo": repo_name,
                "pr_number": pr_number,
                "duration_seconds": round(duration, 3),
                "error": err_msg,
            }


# FastAPI router
router = APIRouter(prefix="/webhook", tags=["Webhook"])

# Pipeline singleton for the router
pipeline_service = WebhookPipeline()


@router.post("/github")
async def github_webhook_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_processing_mode: Optional[str] = Header(None, alias="X-Processing-Mode"),
    sync: bool = False,
):
    """GitHub webhook receiver for pull request merge events."""
    raw_body = await request.body()
    receipt_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    # Generate a fallback delivery ID if not provided by caller
    delivery_id = x_github_delivery or f"deliv-{int(time.time() * 1000)}"
    event_type = x_github_event or "pull_request"

    logger.info(
        "Webhook received at %s | Delivery: %s | Event: %s | Size: %d bytes",
        receipt_time,
        delivery_id,
        event_type,
        len(raw_body),
    )

    # 1. HMAC Signature Verification (when secret is configured)
    if settings.GITHUB_WEBHOOK_SECRET:
        if not x_hub_signature_256:
            logger.warning("Rejected webhook %s: Missing X-Hub-Signature-256 header while secret is configured", delivery_id)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing X-Hub-Signature-256 header"},
            )
        if not verify_github_signature(settings.GITHUB_WEBHOOK_SECRET, raw_body, x_hub_signature_256):
            logger.warning("Rejected webhook %s: HMAC signature mismatch", delivery_id)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid webhook HMAC signature"},
            )

    # 2. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to decode JSON payload for delivery %s: %s", delivery_id, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Malformed JSON payload: {str(exc)}"},
        )

    # 3. Handle GitHub Ping Event
    if event_type == "ping":
        zen = payload.get("zen", "Keep it logically awesome.")
        logger.info("Processed ping event for delivery %s: zen='%s'", delivery_id, zen)
        return {"status": "ok", "message": "pong", "zen": zen}

    # 4. Filter for pull_request events only
    if event_type != "pull_request":
        reason = f"Event type '{event_type}' ignored (only 'pull_request' is handled)"
        logger.info("Delivery %s ignored: %s", delivery_id, reason)
        return {"status": "ignored", "reason": reason}

    # Extract pull request fields
    action = payload.get("action", "")
    pr_dict = payload.get("pull_request") or {}
    is_merged = pr_dict.get("merged") is True
    pr_number = pr_dict.get("number") or payload.get("number") or 0
    repo_dict = payload.get("repository") or {}
    repo_name = repo_dict.get("full_name") or repo_dict.get("name") or "unknown/unknown"
    pr_title = pr_dict.get("title") or f"PR #{pr_number}"
    pr_author = (pr_dict.get("user") or {}).get("login") or (payload.get("sender") or {}).get("login") or "unknown"
    pr_url = pr_dict.get("html_url") or f"https://github.com/{repo_name}/pull/{pr_number}"

    logger.info(
        "Webhook details: delivery=%s, action=%s, repo=%s, pr=#%d, title='%s', merged=%s",
        delivery_id,
        action,
        repo_name,
        pr_number,
        pr_title,
        is_merged,
    )

    # 5. Strict Event Filtering: Run pipeline ONLY when action == 'closed' AND merged is True
    if action != "closed" or not is_merged:
        if action == "closed" and not is_merged:
            reason = f"PR #{pr_number} was closed without being merged"
        else:
            reason = f"Action '{action}' is ignored (only closed and merged PRs are processed)"

        logger.info("Delivery %s ignored: %s", delivery_id, reason)
        await pipeline_service.db.record_ignored(
            delivery_id,
            repo_name,
            pr_number,
            action,
            reason,
            pr_title=pr_title,
            pr_author=pr_author,
            pr_url=pr_url,
        )
        return {"status": "ignored", "reason": reason, "delivery_id": delivery_id}

    # 6. Idempotency Check & Registration
    should_process, reason, existing_record = await pipeline_service.db.register_delivery(
        delivery_id=delivery_id,
        repo=repo_name,
        pr_number=pr_number,
        action=action,
        pr_title=pr_title,
        pr_author=pr_author,
        pr_url=pr_url,
    )

    if not should_process:
        logger.info("Delivery %s skipped by idempotency check: %s", delivery_id, reason)
        return {
            "status": "skipped",
            "reason": reason,
            "delivery_id": delivery_id,
            "existing_status": existing_record.status if existing_record else None,
        }

    # 7. Execute the processing pipeline
    is_sync = sync or (x_processing_mode == "sync")

    if is_sync:
        # Synchronous execution mode (typically for tests requesting immediate inline payload)
        result = await pipeline_service.process_merged_pr(payload, delivery_id)
        return result

    # Default production mode: Timely HTTP 200 acknowledgment with BackgroundTasks
    background_tasks.add_task(pipeline_service.process_merged_pr, payload, delivery_id)
    return {
        "status": "accepted",
        "delivery_id": delivery_id,
        "repo": repo_name,
        "pr_number": pr_number,
        "message": "Webhook accepted for background processing",
    }


@router.get("/delivery/{delivery_id}")
async def get_delivery_status(delivery_id: str):
    """Retrieve processing status and results for a webhook delivery."""
    record = await pipeline_service.db.get_delivery(delivery_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery {delivery_id} not found",
        )
    return record
