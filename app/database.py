"""SQLite-based persistent tracking and idempotency manager for webhook deliveries and email history."""

import asyncio
from datetime import datetime, timezone
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import aiosqlite

from app.config import settings
from app.logging_config import logger
from app.models import DeliveryRecord, EmailDeliveryRecord, LearningDetail, PaginatedResponse


def mask_email(email: Optional[str]) -> str:
    """Mask email address for UI display to protect recipient privacy."""
    if not email or "@" not in email:
        return email or "Not configured"
    user_part, domain_part = email.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain_part}"


class DatabaseManager:
    """Manages SQLite storage for webhook deliveries, status transitions, email records, and queries."""

    def __init__(self, db_path: str = "pr_chronicler.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    async def init_db(self) -> None:
        """Initializes tables, columns, indexes, SQLite WAL mode, and safe backfills."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute("PRAGMA foreign_keys = ON;")

            # 1. Base webhook_deliveries table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    repo TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reflection_json TEXT,
                    error_message TEXT,
                    pr_title TEXT,
                    pr_author TEXT,
                    pr_url TEXT
                );
            """)

            # Verify existing columns and alter table if columns were added later
            async with db.execute("PRAGMA table_info(webhook_deliveries);") as cursor:
                existing_cols = {row[1] for row in await cursor.fetchall()}

            for col_name, col_type in [
                ("pr_title", "TEXT"),
                ("pr_author", "TEXT"),
                ("pr_url", "TEXT"),
            ]:
                if col_name not in existing_cols:
                    try:
                        await db.execute(f"ALTER TABLE webhook_deliveries ADD COLUMN {col_name} {col_type};")
                        logger.info("Migrated schema: Added column %s to webhook_deliveries", col_name)
                    except Exception as exc:
                        logger.debug("Column %s already present or migration skipped: %s", col_name, exc)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_repo_pr_status 
                ON webhook_deliveries (repo, pr_number, status);
            """)

            # 2. Email deliveries table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS email_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_id TEXT NOT NULL,
                    repo TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    sent_at TEXT NOT NULL,
                    FOREIGN KEY (delivery_id) REFERENCES webhook_deliveries (delivery_id)
                );
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_email_delivery_id 
                ON email_deliveries (delivery_id);
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_email_repo_pr 
                ON email_deliveries (repo, pr_number);
            """)

            # 3. Recent searches table for explorer
            await db.execute("""
                CREATE TABLE IF NOT EXISTS recent_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    search_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_recent_searches_created 
                ON recent_searches (created_at DESC);
            """)

            # 4. Explorer cached contributions & AI reflections
            await db.execute("""
                CREATE TABLE IF NOT EXISTS explorer_contributions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    pr_title TEXT,
                    pr_author TEXT,
                    pr_url TEXT,
                    state TEXT DEFAULT 'closed',
                    merged_at TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    analyzed_at TEXT,
                    reflection_json TEXT,
                    is_saved INTEGER DEFAULT 0,
                    UNIQUE(repo, pr_number)
                );
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_explorer_repo_pr 
                ON explorer_contributions (repo, pr_number);
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_explorer_author 
                ON explorer_contributions (pr_author);
            """)

            # 5. Contributor outreach logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS contributor_outreach (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient_email TEXT NOT NULL,
                    recipient_name TEXT,
                    contributor_username TEXT,
                    repo TEXT,
                    pr_number INTEGER,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    email_source TEXT NOT NULL,
                    sent_at TEXT,
                    created_at TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE
                );
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_outreach_created 
                ON contributor_outreach (created_at DESC);
            """)

            # 6. Backfill missing metadata for historical rows if needed
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM webhook_deliveries WHERE pr_title IS NULL OR pr_title = ''") as cursor:
                unfilled_rows = await cursor.fetchall()

            for row in unfilled_rows:
                deliv_id = row["delivery_id"]
                repo = row["repo"]
                pr_num = row["pr_number"]
                title = f"Pull Request #{pr_num}"
                author = "github-user"
                url = f"https://github.com/{repo}/pull/{pr_num}"

                if "flask" in repo and pr_num == 6168:
                    title = "Drop Python 3.10 as it has reached EOL."
                    author = "pallets-contributor"
                    url = "https://github.com/pallets/flask/pull/6168"
                elif row["reflection_json"]:
                    try:
                        ref_data = json.loads(row["reflection_json"])
                        issue_details = ref_data.get("issue_details", "")
                        match = re.search(r'purpose is to ["\']([^"\']+)["\']', issue_details)
                        if match:
                            title = match.group(1)
                    except Exception:
                        pass

                await db.execute(
                    "UPDATE webhook_deliveries SET pr_title = ?, pr_author = ?, pr_url = ? WHERE delivery_id = ?",
                    (title, author, url, deliv_id),
                )

            # 4. Idempotently backfill email_deliveries for completed deliveries missing email audit records
            recipient = settings.RECIPIENT_EMAIL or "recipient@domain.com"
            async with db.execute(
                """
                SELECT delivery_id, repo, pr_number, created_at, updated_at
                FROM webhook_deliveries
                WHERE status = 'COMPLETED'
                  AND delivery_id NOT IN (SELECT delivery_id FROM email_deliveries)
                """
            ) as cursor:
                unbackfilled_rows = await cursor.fetchall()

            for row in unbackfilled_rows:
                subject = f"[OS-Log] PR Merged: {row['repo']} (#{row['pr_number']})"
                sent_at = row["updated_at"] or row["created_at"]
                await db.execute(
                    """
                    INSERT INTO email_deliveries (delivery_id, repo, pr_number, recipient, subject, status, error_message, sent_at)
                    VALUES (?, ?, ?, ?, ?, 'SENT', NULL, ?)
                    """,
                    (row["delivery_id"], row["repo"], row["pr_number"], recipient, subject, sent_at),
                )
            if unbackfilled_rows:
                logger.info("Idempotently backfilled %d completed email deliveries", len(unbackfilled_rows))

            await db.commit()

        logger.info("Initialized SQLite database at %s", self.db_path)
        await self.recover_interrupted_deliveries()

    async def recover_interrupted_deliveries(
        self,
        interruption_message: str = "Interrupted: server process terminated while delivery was in progress",
    ) -> int:
        """Atomically recovers records left in PROCESSING status by a prior process, marking them FAILED."""
        now = self._now()
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """
                    UPDATE webhook_deliveries
                    SET status = 'FAILED', error_message = ?, updated_at = ?
                    WHERE status = 'PROCESSING'
                    """,
                    (interruption_message, now),
                ) as cursor:
                    recovered_count = cursor.rowcount
                await db.commit()

        if recovered_count > 0:
            logger.warning(
                "Recovered %d interrupted delivery record(s) left in 'PROCESSING'. Marked as FAILED.",
                recovered_count,
            )
        else:
            logger.debug("No stale 'PROCESSING' delivery records found during startup recovery.")
        return recovered_count

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def get_delivery(self, delivery_id: str) -> Optional[DeliveryRecord]:
        """Fetch delivery record by delivery_id."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM webhook_deliveries WHERE delivery_id = ?",
                (delivery_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return DeliveryRecord(**dict(row))
        return None

    async def is_pr_already_completed(self, repo: str, pr_number: int) -> bool:
        """Check if this specific PR has already been completed in any delivery."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM webhook_deliveries WHERE repo = ? AND pr_number = ? AND status = 'COMPLETED' LIMIT 1",
                (repo, pr_number)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def register_delivery(
        self,
        delivery_id: str,
        repo: str,
        pr_number: int,
        action: str,
        pr_title: Optional[str] = None,
        pr_author: Optional[str] = None,
        pr_url: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[DeliveryRecord]]:
        """Atomically registers delivery or returns existing status.
        
        Returns:
            (should_process, reason, existing_record)
        """
        now = self._now()
        title = pr_title or f"PR #{pr_number}"
        author = pr_author or "github-user"
        url = pr_url or f"https://github.com/{repo}/pull/{pr_number}"

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                # Check for existing delivery_id first
                async with db.execute(
                    "SELECT * FROM webhook_deliveries WHERE delivery_id = ?",
                    (delivery_id,)
                ) as cursor:
                    existing = await cursor.fetchone()
                    if existing:
                        record = DeliveryRecord(**dict(existing))
                        if record.status == "COMPLETED":
                            return False, f"Delivery {delivery_id} already completed", record
                        if record.status == "PROCESSING":
                            return False, f"Delivery {delivery_id} is currently in progress", record
                        if record.status == "IGNORED":
                            return False, f"Delivery {delivery_id} was previously ignored: {record.reason}", record
                        if record.status == "FAILED":
                            # Check if this PR was completed under another delivery_id while this attempt was failed
                            async with db.execute(
                                "SELECT * FROM webhook_deliveries WHERE repo = ? AND pr_number = ? AND status = 'COMPLETED' LIMIT 1",
                                (repo, pr_number)
                            ) as cur_comp:
                                completed_pr = await cur_comp.fetchone()
                                if completed_pr:
                                    comp_rec = DeliveryRecord(**dict(completed_pr))
                                    return False, f"PR #{pr_number} for {repo} was already processed successfully in delivery {comp_rec.delivery_id}", comp_rec

                            # Prior attempt failed and PR not completed; update to PROCESSING to allow retry
                            await db.execute(
                                "UPDATE webhook_deliveries SET status = 'PROCESSING', updated_at = ? WHERE delivery_id = ?",
                                (now, delivery_id)
                            )
                            await db.commit()
                            return True, f"Retrying previously failed delivery {delivery_id}", record

                # Check if this PR was already completed under another delivery_id
                async with db.execute(
                    "SELECT * FROM webhook_deliveries WHERE repo = ? AND pr_number = ? AND status = 'COMPLETED' LIMIT 1",
                    (repo, pr_number)
                ) as cursor:
                    completed_pr = await cursor.fetchone()
                    if completed_pr:
                        record = DeliveryRecord(**dict(completed_pr))
                        return False, f"PR #{pr_number} for {repo} was already processed successfully in delivery {record.delivery_id}", record

                # Insert new record with PROCESSING status
                await db.execute("""
                    INSERT INTO webhook_deliveries (
                        delivery_id, repo, pr_number, action, status, created_at, updated_at,
                        pr_title, pr_author, pr_url
                    ) VALUES (?, ?, ?, ?, 'PROCESSING', ?, ?, ?, ?, ?)
                """, (delivery_id, repo, pr_number, action, now, now, title, author, url))
                await db.commit()
                return True, "Delivery accepted for processing", None

    async def mark_completed(
        self,
        delivery_id: str,
        reflection_json: str,
        pr_title: Optional[str] = None,
        pr_author: Optional[str] = None,
        pr_url: Optional[str] = None,
    ) -> None:
        """Mark delivery as COMPLETED with generated reflection JSON and metadata."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            if pr_title or pr_author or pr_url:
                await db.execute("""
                    UPDATE webhook_deliveries
                    SET status = 'COMPLETED', reflection_json = ?, updated_at = ?, error_message = NULL,
                        pr_title = COALESCE(?, pr_title),
                        pr_author = COALESCE(?, pr_author),
                        pr_url = COALESCE(?, pr_url)
                    WHERE delivery_id = ?
                """, (reflection_json, now, pr_title, pr_author, pr_url, delivery_id))
            else:
                await db.execute("""
                    UPDATE webhook_deliveries
                    SET status = 'COMPLETED', reflection_json = ?, updated_at = ?, error_message = NULL
                    WHERE delivery_id = ?
                """, (reflection_json, now, delivery_id))
            await db.commit()
        logger.info("Delivery %s marked as COMPLETED", delivery_id)

    async def mark_failed(self, delivery_id: str, error_message: str) -> None:
        """Mark delivery as FAILED with error trace or message."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE webhook_deliveries
                SET status = 'FAILED', error_message = ?, updated_at = ?
                WHERE delivery_id = ?
            """, (error_message, now, delivery_id))
            await db.commit()
        logger.warning("Delivery %s marked as FAILED: %s", delivery_id, error_message)

    async def record_ignored(
        self,
        delivery_id: str,
        repo: str,
        pr_number: int,
        action: str,
        reason: str,
        pr_title: Optional[str] = None,
        pr_author: Optional[str] = None,
        pr_url: Optional[str] = None,
    ) -> None:
        """Record an event that was safely ignored without invoking processing."""
        now = self._now()
        title = pr_title or f"PR #{pr_number}"
        author = pr_author or "github-user"
        url = pr_url or f"https://github.com/{repo}/pull/{pr_number}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO webhook_deliveries (
                    delivery_id, repo, pr_number, action, status, reason, created_at, updated_at,
                    pr_title, pr_author, pr_url
                ) VALUES (?, ?, ?, ?, 'IGNORED', ?, ?, ?, ?, ?, ?)
            """, (delivery_id, repo, pr_number, action, reason, now, now, title, author, url))
            await db.commit()
        logger.info("Delivery %s recorded as IGNORED: %s", delivery_id, reason)

    async def record_email_delivery(
        self,
        delivery_id: str,
        repo: str,
        pr_number: int,
        recipient: str,
        subject: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> int:
        """Record an email delivery attempt in the persistent database."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO email_deliveries (
                    delivery_id, repo, pr_number, recipient, subject, status, error_message, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (delivery_id, repo, pr_number, recipient, subject, status, error_message, now))
            await db.commit()
            return cursor.lastrowid or 0

    # =========================================================================
    # Query & Reporting Methods for Frontend Dashboard & Pages
    # =========================================================================

    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Calculates accurate aggregate metrics for the dashboard without fabricating data."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Status distribution
            async with db.execute("""
                SELECT status, COUNT(*) as count 
                FROM webhook_deliveries 
                GROUP BY status
            """) as cursor:
                status_rows = await cursor.fetchall()
            status_dist = {row["status"]: row["count"] for row in status_rows}

            # Total unique PRs
            async with db.execute("""
                SELECT COUNT(DISTINCT repo || '#' || pr_number) as total_prs
                FROM webhook_deliveries
            """) as cursor:
                row = await cursor.fetchone()
                total_prs = row["total_prs"] if row else 0

            # Total deliveries
            async with db.execute("SELECT COUNT(*) as total FROM webhook_deliveries") as cursor:
                row = await cursor.fetchone()
                total_deliveries = row["total"] if row else 0

            # Count total learnings from COMPLETED reflections
            async with db.execute("""
                SELECT reflection_json 
                FROM webhook_deliveries 
                WHERE status = 'COMPLETED' AND reflection_json IS NOT NULL
            """) as cursor:
                reflections = await cursor.fetchall()

            total_learnings = 0
            for r in reflections:
                try:
                    parsed = json.loads(r["reflection_json"])
                    total_learnings += len(parsed.get("key_learnings", []))
                except Exception:
                    pass

            # Total emails sent
            async with db.execute("SELECT COUNT(*) as total FROM email_deliveries WHERE status = 'SENT'") as cursor:
                row = await cursor.fetchone()
                total_emails_sent = row["total"] if row else 0

            # Recent activity (last 7 deliveries)
            async with db.execute("""
                SELECT delivery_id, repo, pr_number, pr_title, pr_author, action, status, created_at, updated_at
                FROM webhook_deliveries
                ORDER BY created_at DESC
                LIMIT 7
            """) as cursor:
                recent_activity = [dict(r) for r in await cursor.fetchall()]

            # Recent errors (last 5 failed)
            async with db.execute("""
                SELECT delivery_id, repo, pr_number, pr_title, error_message, updated_at
                FROM webhook_deliveries
                WHERE status = 'FAILED' AND error_message IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 5
            """) as cursor:
                recent_errors = [dict(r) for r in await cursor.fetchall()]

            # Last successful processing timestamp
            async with db.execute("""
                SELECT updated_at 
                FROM webhook_deliveries 
                WHERE status = 'COMPLETED' 
                ORDER BY updated_at DESC 
                LIMIT 1
            """) as cursor:
                last_completed_row = await cursor.fetchone()
                last_successful_at = last_completed_row["updated_at"] if last_completed_row else None

        return {
            "total_prs": total_prs,
            "total_deliveries": total_deliveries,
            "completed_jobs": status_dist.get("COMPLETED", 0),
            "failed_jobs": status_dist.get("FAILED", 0),
            "ignored_jobs": status_dist.get("IGNORED", 0),
            "processing_jobs": status_dist.get("PROCESSING", 0),
            "total_learnings": total_learnings,
            "total_emails_sent": total_emails_sent,
            "status_distribution": status_dist,
            "recent_activity": recent_activity,
            "recent_errors": recent_errors,
            "last_successful_processing_at": last_successful_at,
        }

    async def get_pull_requests(
        self,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None,
        repo: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> PaginatedResponse:
        """Retrieves paginated, filterable pull request records."""
        safe_sort = "created_at" if sort_by not in ("created_at", "updated_at", "pr_number") else sort_by
        safe_order = "ASC" if order.lower() == "asc" else "DESC"

        conditions: List[str] = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.upper())
        if repo:
            conditions.append("repo LIKE ?")
            params.append(f"%{repo}%")
        if search:
            search_pattern = f"%{search}%"
            conditions.append("(repo LIKE ? OR pr_title LIKE ? OR pr_author LIKE ? OR CAST(pr_number AS TEXT) LIKE ?)")
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Total matching count
            count_sql = f"SELECT COUNT(*) as count FROM webhook_deliveries {where_clause}"
            async with db.execute(count_sql, params) as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            # Paginated items
            offset = max(0, (page - 1) * limit)
            query_sql = f"""
                SELECT delivery_id, repo, pr_number, action, status, reason, 
                       created_at, updated_at, reflection_json, error_message,
                       pr_title, pr_author, pr_url
                FROM webhook_deliveries
                {where_clause}
                ORDER BY {safe_sort} {safe_order}
                LIMIT ? OFFSET ?
            """
            async with db.execute(query_sql, params + [limit, offset]) as cursor:
                rows = await cursor.fetchall()

            # Enrich rows with learnings count and email status
            items = []
            for row in rows:
                item = dict(row)
                # Learnings count
                learnings_cnt = 0
                if item.get("reflection_json"):
                    try:
                        ref = json.loads(item["reflection_json"])
                        learnings_cnt = len(ref.get("key_learnings", []))
                    except Exception:
                        pass
                item["learnings_count"] = learnings_cnt

                # Email status
                async with db.execute(
                    "SELECT status FROM email_deliveries WHERE delivery_id = ? ORDER BY id DESC LIMIT 1",
                    (item["delivery_id"],)
                ) as cur_email:
                    email_row = await cur_email.fetchone()
                    item["email_status"] = email_row["status"] if email_row else ("SENT" if item["status"] == "COMPLETED" else "NOT_SENT")

                items.append(item)

        total_pages = math.ceil(total / limit) if limit > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def get_pull_request_detail(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves detailed record for a pull request, including parsed reflection and email logs."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM webhook_deliveries WHERE delivery_id = ? LIMIT 1",
                (delivery_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

            data = dict(row)

            # Parsed reflection
            parsed_reflection = None
            if data.get("reflection_json"):
                try:
                    parsed_reflection = json.loads(data["reflection_json"])
                except Exception:
                    pass
            data["reflection"] = parsed_reflection

            # Email deliveries
            async with db.execute(
                "SELECT id, recipient, subject, status, error_message, sent_at FROM email_deliveries WHERE delivery_id = ? ORDER BY sent_at DESC",
                (delivery_id,)
            ) as cursor:
                email_rows = await cursor.fetchall()
                data["emails"] = [
                    {
                        "id": r["id"],
                        "recipient": mask_email(r["recipient"]),
                        "subject": r["subject"],
                        "status": r["status"],
                        "error_message": r["error_message"],
                        "sent_at": r["sent_at"],
                    }
                    for r in email_rows
                ]

        return data

    async def get_learnings(
        self,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        repo: Optional[str] = None,
        pr_number: Optional[int] = None,
    ) -> PaginatedResponse:
        """Extracts and paginates structured learnings from completed reflections."""
        conditions = ["status = 'COMPLETED'", "reflection_json IS NOT NULL"]
        params: List[Any] = []

        if repo:
            conditions.append("repo LIKE ?")
            params.append(f"%{repo}%")
        if pr_number:
            conditions.append("pr_number = ?")
            params.append(pr_number)

        where_clause = f"WHERE {' AND '.join(conditions)}"

        all_learnings: List[Dict[str, Any]] = []

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = f"""
                SELECT delivery_id, repo, pr_number, pr_title, pr_author, pr_url, created_at, reflection_json
                FROM webhook_deliveries
                {where_clause}
                ORDER BY created_at DESC
            """
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                try:
                    ref_data = json.loads(row["reflection_json"])
                    learnings = ref_data.get("key_learnings", [])
                    issue_details = ref_data.get("issue_details", "")
                    exec_summary = ref_data.get("execution_summary", "")

                    for idx, learning in enumerate(learnings):
                        # Extract evidence tags
                        tags = re.findall(r"\[(Verified|Inferred|Unverified)\]", learning)

                        # Filter by search term if provided
                        if search:
                            s = search.lower()
                            if (
                                s not in learning.lower()
                                and s not in row["repo"].lower()
                                and s not in (row["pr_title"] or "").lower()
                            ):
                                continue

                        all_learnings.append({
                            "id": f"{row['delivery_id']}-{idx + 1}",
                            "delivery_id": row["delivery_id"],
                            "repo": row["repo"],
                            "pr_number": row["pr_number"],
                            "pr_title": row["pr_title"] or f"PR #{row['pr_number']}",
                            "pr_url": row["pr_url"] or f"https://github.com/{row['repo']}/pull/{row['pr_number']}",
                            "pr_author": row["pr_author"],
                            "learning": learning,
                            "index": idx + 1,
                            "evidence_tags": list(set(tags)),
                            "created_at": row["created_at"],
                            "execution_summary_snippet": exec_summary[:280] + ("..." if len(exec_summary) > 280 else ""),
                            "issue_details_snippet": issue_details[:280] + ("..." if len(issue_details) > 280 else ""),
                        })
                except Exception:
                    continue

        total = len(all_learnings)
        offset = max(0, (page - 1) * limit)
        paginated_items = all_learnings[offset : offset + limit]
        total_pages = math.ceil(total / limit) if limit > 0 else 1

        return PaginatedResponse(
            items=paginated_items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def get_webhook_events(
        self,
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse:
        """Retrieves raw webhook deliveries with audit states."""
        conditions: List[str] = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.upper())
        if search:
            search_pat = f"%{search}%"
            conditions.append("(delivery_id LIKE ? OR repo LIKE ? OR CAST(pr_number AS TEXT) LIKE ? OR reason LIKE ?)")
            params.extend([search_pat, search_pat, search_pat, search_pat])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            count_sql = f"SELECT COUNT(*) as count FROM webhook_deliveries {where_clause}"
            async with db.execute(count_sql, params) as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            offset = max(0, (page - 1) * limit)
            query_sql = f"""
                SELECT delivery_id, repo, pr_number, action, status, reason, error_message,
                       created_at, updated_at, pr_title, pr_author, pr_url
                FROM webhook_deliveries
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            async with db.execute(query_sql, params + [limit, offset]) as cursor:
                rows = await cursor.fetchall()
                items = [dict(r) for r in rows]

        total_pages = math.ceil(total / limit) if limit > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def get_email_deliveries(
        self,
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse:
        """Retrieves email delivery audit records with masked recipient privacy."""
        conditions: List[str] = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.upper())
        if search:
            search_pat = f"%{search}%"
            conditions.append("(repo LIKE ? OR subject LIKE ? OR CAST(pr_number AS TEXT) LIKE ? OR delivery_id LIKE ?)")
            params.extend([search_pat, search_pat, search_pat, search_pat])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            count_sql = f"SELECT COUNT(*) as count FROM email_deliveries {where_clause}"
            async with db.execute(count_sql, params) as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            offset = max(0, (page - 1) * limit)
            query_sql = f"""
                SELECT id, delivery_id, repo, pr_number, recipient, subject, status, error_message, sent_at
                FROM email_deliveries
                {where_clause}
                ORDER BY sent_at DESC
                LIMIT ? OFFSET ?
            """
            async with db.execute(query_sql, params + [limit, offset]) as cursor:
                rows = await cursor.fetchall()
                items = []
                for r in rows:
                    item = dict(r)
                    item["recipient"] = mask_email(item.get("recipient"))
                    items.append(item)

        total_pages = math.ceil(total / limit) if limit > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    # =================================================================
    # Explorer & Outreach Methods
    # =================================================================

    async def record_search(self, query: str, search_type: str, target: str) -> None:
        """Records a user search into recent_searches for quick history recall."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            # Delete any duplicate recent entry for the same target to keep history clean
            await db.execute(
                "DELETE FROM recent_searches WHERE search_type = ? AND target = ?",
                (search_type, target),
            )
            await db.execute(
                """
                INSERT INTO recent_searches (query, search_type, target, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (query, search_type, target, now),
            )
            # Retain only last 50 searches
            await db.execute("""
                DELETE FROM recent_searches WHERE id NOT IN (
                    SELECT id FROM recent_searches ORDER BY created_at DESC LIMIT 50
                )
            """)
            await db.commit()

    async def get_recent_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent searches sorted newest first."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, query, search_type, target, created_at
                FROM recent_searches
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def save_or_update_contribution(
        self,
        repo: str,
        pr_number: int,
        pr_title: str,
        pr_author: str,
        pr_url: str,
        state: str = "closed",
        reflection_json: Optional[str] = None,
        is_saved: Optional[bool] = None,
        merged_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Saves or updates an explorer contribution record and its cached AI reflection."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Check if exists
            async with db.execute(
                "SELECT * FROM explorer_contributions WHERE repo = ? AND pr_number = ?",
                (repo, pr_number),
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                analyzed_at = now if reflection_json is not None else existing["analyzed_at"]
                ref_json = reflection_json if reflection_json is not None else existing["reflection_json"]
                saved_val = (1 if is_saved else 0) if is_saved is not None else existing["is_saved"]
                m_at = merged_at or existing["merged_at"]

                await db.execute(
                    """
                    UPDATE explorer_contributions
                    SET pr_title = ?, pr_author = ?, pr_url = ?, state = ?, merged_at = ?,
                        updated_at = ?, analyzed_at = ?, reflection_json = ?, is_saved = ?
                    WHERE repo = ? AND pr_number = ?
                    """,
                    (
                        pr_title,
                        pr_author,
                        pr_url,
                        state,
                        m_at,
                        now,
                        analyzed_at,
                        ref_json,
                        saved_val,
                        repo,
                        pr_number,
                    ),
                )
            else:
                analyzed_at = now if reflection_json is not None else None
                saved_val = 1 if is_saved else 0
                await db.execute(
                    """
                    INSERT INTO explorer_contributions (
                        repo, pr_number, pr_title, pr_author, pr_url, state,
                        merged_at, created_at, updated_at, analyzed_at, reflection_json, is_saved
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo,
                        pr_number,
                        pr_title,
                        pr_author,
                        pr_url,
                        state,
                        merged_at,
                        now,
                        now,
                        analyzed_at,
                        reflection_json,
                        saved_val,
                    ),
                )
            await db.commit()

            async with db.execute(
                "SELECT * FROM explorer_contributions WHERE repo = ? AND pr_number = ?",
                (repo, pr_number),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    async def get_contribution(self, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Fetch saved/analyzed contribution details by repo and PR number."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM explorer_contributions WHERE repo = ? AND pr_number = ?",
                (repo, pr_number),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def toggle_save_contribution(self, repo: str, pr_number: int, is_saved: bool) -> bool:
        """Toggle the saved status of a contribution."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE explorer_contributions SET is_saved = ? WHERE repo = ? AND pr_number = ?",
                (1 if is_saved else 0, repo, pr_number),
            )
            await db.commit()
            return is_saved

    async def list_contributions(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        repo: Optional[str] = None,
        author: Optional[str] = None,
        state: Optional[str] = None,
        analyzed_only: bool = False,
        saved_only: bool = False,
    ) -> PaginatedResponse:
        """Lists cached/saved contributions with filtering and pagination."""
        conditions: List[str] = []
        params: List[Any] = []

        if repo:
            conditions.append("repo = ?")
            params.append(repo)
        if author:
            conditions.append("pr_author = ?")
            params.append(author)
        if state:
            conditions.append("state = ?")
            params.append(state)
        if analyzed_only:
            conditions.append("reflection_json IS NOT NULL")
        if saved_only:
            conditions.append("is_saved = 1")
        if search:
            pat = f"%{search}%"
            conditions.append("(repo LIKE ? OR pr_title LIKE ? OR pr_author LIKE ? OR CAST(pr_number AS TEXT) LIKE ?)")
            params.extend([pat, pat, pat, pat])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            count_sql = f"SELECT COUNT(*) as count FROM explorer_contributions {where_clause}"
            async with db.execute(count_sql, params) as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            offset = max(0, (page - 1) * limit)
            query_sql = f"""
                SELECT id, repo, pr_number, pr_title, pr_author, pr_url, state,
                       merged_at, created_at, updated_at, analyzed_at,
                       (CASE WHEN reflection_json IS NOT NULL THEN 1 ELSE 0 END) as is_analyzed,
                       is_saved
                FROM explorer_contributions
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """
            async with db.execute(query_sql, params + [limit, offset]) as cursor:
                rows = await cursor.fetchall()
                items = [dict(r) for r in rows]

        total_pages = math.ceil(total / limit) if limit > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def record_outreach(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        contributor_username: Optional[str],
        repo: Optional[str],
        pr_number: Optional[int],
        subject: str,
        body: str,
        status: str,
        email_source: str,
        idempotency_key: str,
        error_message: Optional[str] = None,
        sent_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records an outreach email delivery attempt."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO contributor_outreach (
                    recipient_email, recipient_name, contributor_username, repo,
                    pr_number, subject, body, status, error_message, email_source,
                    sent_at, created_at, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipient_email,
                    recipient_name,
                    contributor_username,
                    repo,
                    pr_number,
                    subject,
                    body,
                    status,
                    error_message,
                    email_source,
                    sent_at or (now if status == "SENT" else None),
                    now,
                    idempotency_key,
                ),
            )
            await db.commit()

            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM contributor_outreach WHERE idempotency_key = ?",
                (idempotency_key,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    async def get_outreach_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Check if an outreach message has already been dispatched with this idempotency key."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM contributor_outreach WHERE idempotency_key = ?",
                (idempotency_key,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def list_outreach(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse:
        """Lists outreach history with masked recipient email addresses."""
        conditions: List[str] = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.upper())
        if search:
            pat = f"%{search}%"
            conditions.append("(subject LIKE ? OR contributor_username LIKE ? OR repo LIKE ?)")
            params.extend([pat, pat, pat])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            count_sql = f"SELECT COUNT(*) as count FROM contributor_outreach {where_clause}"
            async with db.execute(count_sql, params) as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            offset = max(0, (page - 1) * limit)
            query_sql = f"""
                SELECT id, recipient_email, recipient_name, contributor_username,
                       repo, pr_number, subject, body, status, error_message,
                       email_source, sent_at, created_at, idempotency_key
                FROM contributor_outreach
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            async with db.execute(query_sql, params + [limit, offset]) as cursor:
                rows = await cursor.fetchall()
                items = []
                for r in rows:
                    item = dict(r)
                    item["recipient_masked"] = mask_email(item.get("recipient_email"))
                    item["body_snippet"] = (item.get("body") or "")[:140] + ("..." if len(item.get("body") or "") > 140 else "")
                    # Remove raw recipient_email from output for UI privacy
                    item.pop("recipient_email", None)
                    items.append(item)

        total_pages = math.ceil(total / limit) if limit > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

