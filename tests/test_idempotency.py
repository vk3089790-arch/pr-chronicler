"""Tests for SQLite-based idempotency, delivery deduplication, and retry behavior."""

import asyncio
import pytest
from app.database import DatabaseManager


@pytest.mark.asyncio
async def test_idempotency_workflow(temp_db):
    """Test full registration, completion, and duplicate suppression cycle."""
    delivery_id = "deliv-uuid-001"
    repo = "acme/api"
    pr_number = 42
    action = "closed"

    # 1. Initial delivery should be accepted
    should_process, reason, existing = await temp_db.register_delivery(
        delivery_id, repo, pr_number, action
    )
    assert should_process is True
    assert existing is None

    # 2. Duplicate while PROCESSING should be rejected
    should_process_2, reason_2, existing_2 = await temp_db.register_delivery(
        delivery_id, repo, pr_number, action
    )
    assert should_process_2 is False
    assert "currently in progress" in reason_2
    assert existing_2.status == "PROCESSING"

    # 3. Mark delivery as COMPLETED
    reflection_json = '{"issue_details": "Fix", "execution_summary": "Done", "key_learnings": ["L1", "L2", "L3"]}'
    await temp_db.mark_completed(delivery_id, reflection_json)

    # 4. Duplicate delivery with the SAME delivery_id after completion should be rejected
    should_process_3, reason_3, existing_3 = await temp_db.register_delivery(
        delivery_id, repo, pr_number, action
    )
    assert should_process_3 is False
    assert "already completed" in reason_3
    assert existing_3.status == "COMPLETED"

    # 5. Delivery with a DIFFERENT delivery_id for the same completed PR should also be rejected
    new_delivery_id = "deliv-uuid-002"
    should_process_4, reason_4, existing_4 = await temp_db.register_delivery(
        new_delivery_id, repo, pr_number, action
    )
    assert should_process_4 is False
    assert f"PR #{pr_number} for {repo} was already processed successfully" in reason_4


@pytest.mark.asyncio
async def test_failed_delivery_allows_retry(temp_db):
    """Test that a failed delivery can be retried cleanly."""
    delivery_id = "deliv-uuid-fail"
    repo = "acme/api"
    pr_number = 99
    action = "closed"

    # 1. Register delivery
    should_process, _, _ = await temp_db.register_delivery(
        delivery_id, repo, pr_number, action
    )
    assert should_process is True

    # 2. Mark as failed
    await temp_db.mark_failed(delivery_id, "Gemini API quota exceeded")

    record = await temp_db.get_delivery(delivery_id)
    assert record.status == "FAILED"
    assert "Gemini API quota exceeded" in record.error_message

    # 3. Retry with same delivery ID should now be accepted
    should_retry, reason, _ = await temp_db.register_delivery(
        delivery_id, repo, pr_number, action
    )
    assert should_retry is True
    assert "Retrying previously failed delivery" in reason

    updated = await temp_db.get_delivery(delivery_id)
    assert updated.status == "PROCESSING"


@pytest.mark.asyncio
async def test_record_ignored_event(temp_db):
    """Test recording of ignored webhook events."""
    delivery_id = "deliv-ignored-1"
    await temp_db.record_ignored(
        delivery_id=delivery_id,
        repo="acme/api",
        pr_number=50,
        action="opened",
        reason="Action 'opened' is ignored",
    )

    record = await temp_db.get_delivery(delivery_id)
    assert record is not None
    assert record.status == "IGNORED"
    assert "Action 'opened' is ignored" in record.reason


@pytest.mark.asyncio
async def test_recover_interrupted_deliveries_lifecycle(temp_db):
    """Test that stale PROCESSING records are marked FAILED on recovery, while COMPLETED and IGNORED are preserved."""
    # 1. Setup in-flight (PROCESSING) record
    proc_id = "deliv-stale-processing"
    await temp_db.register_delivery(proc_id, "acme/api", 10, "closed")

    # 2. Setup COMPLETED record
    comp_id = "deliv-completed-untouched"
    await temp_db.register_delivery(comp_id, "acme/api", 20, "closed")
    await temp_db.mark_completed(comp_id, '{"summary": "done"}')

    # 3. Setup IGNORED record
    ign_id = "deliv-ignored-untouched"
    await temp_db.record_ignored(ign_id, "acme/api", 30, "opened", "Action 'opened' ignored")

    # Verify initial states
    r_proc = await temp_db.get_delivery(proc_id)
    r_comp = await temp_db.get_delivery(comp_id)
    r_ign = await temp_db.get_delivery(ign_id)
    assert r_proc.status == "PROCESSING"
    assert r_comp.status == "COMPLETED"
    assert r_ign.status == "IGNORED"

    # 4. Trigger recovery
    recovered_count = await temp_db.recover_interrupted_deliveries()
    assert recovered_count == 1

    # 5. Verify PROCESSING transitioned to FAILED with clear message
    r_proc_after = await temp_db.get_delivery(proc_id)
    assert r_proc_after.status == "FAILED"
    assert "Interrupted: server process terminated" in r_proc_after.error_message

    # 6. Verify COMPLETED and IGNORED records are completely untouched
    r_comp_after = await temp_db.get_delivery(comp_id)
    assert r_comp_after.status == "COMPLETED"
    assert r_comp_after.reflection_json == '{"summary": "done"}'

    r_ign_after = await temp_db.get_delivery(ign_id)
    assert r_ign_after.status == "IGNORED"
    assert r_ign_after.reason == "Action 'opened' ignored"

    # 7. Verify that the recovered delivery can be retried cleanly
    should_retry, reason, _ = await temp_db.register_delivery(proc_id, "acme/api", 10, "closed")
    assert should_retry is True
    assert "Retrying previously failed delivery" in reason

    r_proc_retried = await temp_db.get_delivery(proc_id)
    assert r_proc_retried.status == "PROCESSING"


@pytest.mark.asyncio
async def test_startup_recovery_in_init_db(tmp_path):
    """Test that init_db automatically recovers interrupted records on startup."""
    db_path = str(tmp_path / "startup_recovery.db")
    db1 = DatabaseManager(db_path)
    await db1.init_db()

    # Create a delivery left in PROCESSING
    stale_id = "deliv-crash-simulation"
    await db1.register_delivery(stale_id, "pallets/flask", 6168, "closed")
    assert (await db1.get_delivery(stale_id)).status == "PROCESSING"

    # Simulate server restart: new DatabaseManager instance initializes DB
    db2 = DatabaseManager(db_path)
    await db2.init_db()

    # Record should have been automatically recovered to FAILED
    record = await db2.get_delivery(stale_id)
    assert record.status == "FAILED"
    assert "Interrupted: server process terminated while delivery was in progress" in record.error_message


@pytest.mark.asyncio
async def test_repeated_init_db_never_duplicates_email_records(tmp_path):
    """Test that repeated init_db calls are strictly idempotent and never duplicate email delivery records."""
    import aiosqlite
    db_path = str(tmp_path / "repeated_init.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    # Create a completed delivery
    deliv_id = "deliv-completed-idempotency"
    await db.register_delivery(deliv_id, "acme/api", 42, "closed")
    await db.mark_completed(deliv_id, '{"issue_details": "Fix", "execution_summary": "Done", "key_learnings": ["L1", "L2", "L3"]}')

    # First init_db should backfill exactly 1 email delivery
    await db.init_db()
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM email_deliveries WHERE delivery_id = ?", (deliv_id,)) as cur:
            count_1 = (await cur.fetchone())[0]
    assert count_1 == 1

    # Second and third init_db runs should NOT create duplicate email deliveries
    await db.init_db()
    await db.init_db()
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM email_deliveries WHERE delivery_id = ?", (deliv_id,)) as cur:
            count_2 = (await cur.fetchone())[0]
    assert count_2 == 1


@pytest.mark.asyncio
async def test_failed_delivery_retry_rejected_if_pr_completed_by_another_delivery(temp_db):
    """Test that retrying a failed delivery is rejected if another delivery completed the PR in the interim."""
    repo = "acme/retry-race"
    pr_num = 77

    # 1. First delivery fails
    deliv_1 = "deliv-failed-attempt"
    await temp_db.register_delivery(deliv_1, repo, pr_num, "closed")
    await temp_db.mark_failed(deliv_1, "Transient network timeout")

    # 2. Second delivery for same PR arrives and completes
    deliv_2 = "deliv-successful-attempt"
    should_proc_2, _, _ = await temp_db.register_delivery(deliv_2, repo, pr_num, "closed")
    assert should_proc_2 is True
    await temp_db.mark_completed(deliv_2, '{"key_learnings": ["L1", "L2", "L3"]}')

    # 3. Retry of first delivery arrives: should be REJECTED because PR is already completed
    should_retry_1, reason_1, rec_1 = await temp_db.register_delivery(deliv_1, repo, pr_num, "closed")
    assert should_retry_1 is False
    assert f"PR #{pr_num} for {repo} was already processed successfully" in reason_1
    assert rec_1.status == "COMPLETED"


@pytest.mark.asyncio
async def test_sqlite_foreign_key_enforcement(tmp_path):
    """Test that foreign key enforcement is active in SQLite."""
    import aiosqlite
    db_path = str(tmp_path / "fk_test.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON;")
        # Attempting to insert an email delivery for a non-existent delivery_id must fail
        with pytest.raises(Exception) as excinfo:
            await conn.execute(
                """
                INSERT INTO email_deliveries (delivery_id, repo, pr_number, recipient, subject, status, sent_at)
                VALUES ('non-existent-deliv-id', 'test/repo', 1, 'a@b.com', 'Subject', 'SENT', '2026-01-01')
                """
            )
            await conn.commit()
        assert "FOREIGN KEY constraint failed" in str(excinfo.value)


