import os
import uuid
import asyncio
import tempfile
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from alembic.config import Config
from alembic import command

from backend.app.db.base import Base
from backend.app.models.job import Job, JobSource
from backend.app.models.automation import AutomationRun
from backend.app.models.notification import Notification
from backend.app.models.enums import AutomationRunStatus, NotificationType, NotificationChannel
from backend.app.services.notification_service import NotificationService


def test_disposable_database_migration_forward_backward():
    """
    Step 4: Disposable database migration test.
    - Uses an isolated temporary SQLite database file.
    - Migrates up to 3f63fd0f4fae.
    - Inserts pre-existing notification records under old schema.
    - Migrates to 4b81cf738a92.
    - Verifies data integrity, column defaults, downgrade, and re-upgrade.
    """
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db_path = tmp_file.name
    tmp_file.close()  # Release Windows file lock

    try:
        sync_url = f"sqlite:///{tmp_db_path.replace(os.sep, '/')}"

        # Configure Alembic pointing to the temporary database
        ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        script_loc = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic"))
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic_cfg.set_main_option("script_location", script_loc)

        # 1. Upgrade to revision 3f63fd0f4fae (prior to Phase 7)
        command.upgrade(alembic_cfg, "3f63fd0f4fae")

        # 2. Insert representative legacy pre-existing data into old notifications table
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO notifications (id, title, message, channel, status, metadata_json, created_at, updated_at)
                    VALUES (:id, :title, :message, :channel, :status, :metadata_json, :created_at, :updated_at)
                    """
                ),
                {
                    "id": "legacy-notif-1",
                    "title": "Legacy Alert",
                    "message": "Pre-existing notification message",
                    "channel": "IN_APP",
                    "status": "DELIVERED",
                    "metadata_json": "{}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            conn.commit()

        # 3. Upgrade to 4b81cf738a92 (Phase 7 notification enhancements & dedup)
        command.upgrade(alembic_cfg, "4b81cf738a92")

        # 4. Verify existing data preserved and new defaults applied
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, title, is_read, is_dismissed, notification_type, dedup_key FROM notifications WHERE id = 'legacy-notif-1'")
            ).fetchone()
            assert row is not None
            assert row[0] == "legacy-notif-1"
            assert row[1] == "Legacy Alert"
            assert row[2] == 0 or row[2] is False  # is_read default False
            assert row[3] == 0 or row[3] is False  # is_dismissed default False
            assert row[4] == "NEW_MATCH"  # notification_type server default

        # 5. Verify downgrade back to 3f63fd0f4fae
        command.downgrade(alembic_cfg, "3f63fd0f4fae")
        with engine.connect() as conn:
            row_downgraded = conn.execute(
                text("SELECT id, title FROM notifications WHERE id = 'legacy-notif-1'")
            ).fetchone()
            assert row_downgraded is not None
            assert row_downgraded[0] == "legacy-notif-1"

        # 6. Verify re-upgrade back to head
        command.upgrade(alembic_cfg, "head")
        engine.dispose()

    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass


@pytest.mark.asyncio
async def test_notification_foreign_key_on_delete_set_null(db_session: AsyncSession):
    """
    Step 4: Tests FK set null behavior.
    When a Job or AutomationRun referenced by a Notification is deleted,
    the Notification's FK must be set to NULL rather than deleting the notification.
    """
    # 1. Create a JobSource & Job
    source = JobSource(
        identifier=f"src_{uuid.uuid4().hex[:6]}",
        name="Test Board",
        base_url="https://test.example.com",
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    job = Job(
        source_id=source.id,
        external_id=f"ext_{uuid.uuid4().hex[:6]}",
        title="Senior Site Reliability Engineer",
        company="Reliability Corp",
        canonical_url="https://test.example.com/jobs/1",
        description="Kubernetes, Linux, Python reliability",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # 2. Create an AutomationRun
    run = AutomationRun(
        run_type="discovery_manual",
        status=AutomationRunStatus.COMPLETED.value,
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    # 3. Create a Notification referencing both
    notif = await NotificationService.create_notification(
        session=db_session,
        title="Job Match Notification",
        message="Job matched successfully",
        notification_type=NotificationType.NEW_MATCH,
        job_id=job.id,
        run_id=run.id,
        dedup_key=f"fk_test_{uuid.uuid4().hex[:8]}",
    )
    assert notif.job_id == job.id
    assert notif.run_id == run.id

    # 4. Delete the referenced Job
    await db_session.delete(job)
    await db_session.commit()

    # 5. Refresh Notification: job_id should now be NULL, notification remains intact
    await db_session.refresh(notif)
    assert notif.job_id is None
    assert notif.title == "Job Match Notification"

    # 6. Delete the referenced AutomationRun
    await db_session.delete(run)
    await db_session.commit()

    await db_session.refresh(notif)
    assert notif.run_id is None
    assert notif.id is not None


@pytest.mark.asyncio
async def test_concurrent_notification_deduplication():
    """
    Step 4: Tests that concurrent notification creation calls with the same dedup_key
    safely resolve to a single persistent record without database errors across distinct transactions.
    """
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db_path = tmp_file.name
    tmp_file.close()

    tmp_async_url = f"sqlite+aiosqlite:///{tmp_db_path.replace(os.sep, '/')}"
    concurrency_engine = create_async_engine(tmp_async_url)
    ConcurrencySession = async_sessionmaker(bind=concurrency_engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with concurrency_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        shared_key = f"concurrent_dedup_{uuid.uuid4().hex}"

        async def create_attempt():
            async with ConcurrencySession() as session:
                return await NotificationService.create_notification(
                    session=session,
                    title="Concurrent Alert",
                    message="Testing concurrency race condition safety",
                    notification_type=NotificationType.NEW_MATCH,
                    dedup_key=shared_key,
                )

        # Execute 5 concurrent notification creation attempts
        results = await asyncio.gather(*(create_attempt() for _ in range(5)))

        # All returned objects must share the exact same database ID
        first_id = results[0].id
        for res in results:
            assert res.id == first_id

        # Verify only 1 record exists in DB with this dedup_key
        async with ConcurrencySession() as session:
            query = select(Notification).where(Notification.dedup_key == shared_key)
            res = await session.execute(query)
            all_matching = res.scalars().all()
            assert len(all_matching) == 1

        await concurrency_engine.dispose()
    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass


def test_disposable_migration_c14fd127ea45_to_d823fa19b2e4():
    """
    Verifies upgrade from c14fd127ea45 to d823fa19b2e4 on an isolated disposable database copy,
    validates column defaults, tests clean downgrade, and verifies re-upgrade to head.
    Never modifies user's actual database.
    """
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db_path = tmp_file.name
    tmp_file.close()

    try:
        sync_url = f"sqlite:///{tmp_db_path.replace(os.sep, '/')}"
        ini_path = os.path.abspath("backend/alembic.ini")
        script_loc = os.path.abspath("backend/alembic")

        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        alembic_cfg.set_main_option("script_location", script_loc)

        # 1. Upgrade to revision c14fd127ea45
        command.upgrade(alembic_cfg, "c14fd127ea45")

        engine = create_engine(sync_url)
        with engine.connect() as conn:
            cols_before = [row[1] for row in conn.execute(text("PRAGMA table_info(job_sources)")).fetchall()]
            assert "source_type" not in cols_before
            assert "integration_status" not in cols_before

            # Insert legacy record under c14fd127ea45
            conn.execute(
                text(
                    "INSERT INTO job_sources (id, identifier, name, base_url, rate_limit_rpm, is_enabled, config_json, jobs_discovered_count, jobs_relevant_count, created_at, updated_at) "
                    "VALUES ('src-legacy-1', 'naukri', 'Naukri.com', 'https://naukri.com', 30, 1, '{}', 0, 0, :dt, :dt)"
                ),
                {"dt": datetime.now(timezone.utc).isoformat()},
            )
            conn.commit()

        # 2. Upgrade to d823fa19b2e4 (head)
        command.upgrade(alembic_cfg, "d823fa19b2e4")

        with engine.connect() as conn:
            cols_after = [row[1] for row in conn.execute(text("PRAGMA table_info(job_sources)")).fetchall()]
            assert "source_type" in cols_after
            assert "integration_status" in cols_after

            row = conn.execute(
                text("SELECT identifier, source_type, integration_status FROM job_sources WHERE id = 'src-legacy-1'")
            ).fetchone()
            assert row is not None
            assert row[0] == "naukri"
            assert row[1] == "job_board"
            assert row[2] == "AVAILABLE"

        # 3. Downgrade back to c14fd127ea45
        command.downgrade(alembic_cfg, "c14fd127ea45")

        with engine.connect() as conn:
            cols_down = [row[1] for row in conn.execute(text("PRAGMA table_info(job_sources)")).fetchall()]
            assert "source_type" not in cols_down
            assert "integration_status" not in cols_down

            row_down = conn.execute(text("SELECT id, identifier FROM job_sources WHERE id = 'src-legacy-1'")).fetchone()
            assert row_down is not None
            assert row_down[1] == "naukri"

        # 4. Re-upgrade back to d823fa19b2e4
        command.upgrade(alembic_cfg, "d823fa19b2e4")

        with engine.connect() as conn:
            cols_reup = [row[1] for row in conn.execute(text("PRAGMA table_info(job_sources)")).fetchall()]
            assert "source_type" in cols_reup
            assert "integration_status" in cols_reup

        engine.dispose()
    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass
