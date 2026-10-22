"""SQLite-based persistent tracking and idempotency manager for webhook deliveries."""

import asyncio
from datetime import datetime, timezone
import os
from typing import Optional, Tuple
import aiosqlite

from app.logging_config import logger
from app.models import DeliveryRecord


class DatabaseManager:
    """Manages SQLite storage for webhook deliveries, status transitions, and idempotency."""

    def __init__(self, db_path: str = "pr_chronicler.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    async def init_db(self) -> None:
        """Initializes tables, indexes, and SQLite WAL mode for concurrency."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
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
                    error_message TEXT
                );
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_repo_pr_status 
                ON webhook_deliveries (repo, pr_number, status);
            """)
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
    ) -> Tuple[bool, str, Optional[DeliveryRecord]]:
        """Atomically registers delivery or returns existing status.
        
        Returns:
            (should_process, reason, existing_record)
        """
        now = self._now()
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
                            # Prior attempt failed; update to PROCESSING to allow retry
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
                        delivery_id, repo, pr_number, action, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'PROCESSING', ?, ?)
                """, (delivery_id, repo, pr_number, action, now, now))
                await db.commit()
                return True, "Delivery accepted for processing", None

    async def mark_completed(self, delivery_id: str, reflection_json: str) -> None:
        """Mark delivery as COMPLETED with generated reflection JSON."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
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
    ) -> None:
        """Record an event that was safely ignored without invoking processing."""
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO webhook_deliveries (
                    delivery_id, repo, pr_number, action, status, reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'IGNORED', ?, ?, ?)
            """, (delivery_id, repo, pr_number, action, reason, now, now))
            await db.commit()
        logger.info("Delivery %s recorded as IGNORED: %s", delivery_id, reason)
