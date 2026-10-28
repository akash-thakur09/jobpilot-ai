import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.job import Job, JobSource, JobDuplicateCluster
from backend.app.models.enums import DuplicateConfidence, ClusterStatus
from backend.app.services.duplicate_detection_service import DuplicateDetectionService


def test_canonicalize_company_and_title():
    # Corporate suffix stripping
    assert DuplicateDetectionService.canonicalize_company("Acme Technologies, Inc.") == "acme"
    assert DuplicateDetectionService.canonicalize_company("Globex Corporation") == "globex"
    assert DuplicateDetectionService.canonicalize_company("Initech LLC") == "initech"
    assert DuplicateDetectionService.canonicalize_company("Stripe, Inc.") == "stripe"
    assert DuplicateDetectionService.canonicalize_company("A & B Solutions") == "a and b"

    # Title normalization
    assert DuplicateDetectionService.canonicalize_title("Senior Python Engineer (Remote)") == "senior python engineer"
    assert DuplicateDetectionService.canonicalize_title("Sr. Backend Developer [Full-time]") == "senior backend developer"
    assert DuplicateDetectionService.canonicalize_title("Lead Software Architect (m/w/d)") == "lead software architect"


def test_canonicalize_url():
    u1 = "https://www.example.com/jobs/123/?utm_source=linkedin&utm_campaign=winter"
    u2 = "http://example.com/jobs/123"
    assert DuplicateDetectionService.canonicalize_url(u1) == "https://example.com/jobs/123"
    assert DuplicateDetectionService.canonicalize_url(u2) == "https://example.com/jobs/123"


def test_exact_canonical_url_duplicate():
    j1 = Job(
        id="j1",
        title="Python Engineer",
        company="Stripe",
        canonical_url="https://stripe.com/jobs/123?utm_source=indeed",
        location="Remote",
        remote_type="REMOTE",
        description="FastAPI role.",
    )
    j2 = Job(
        id="j2",
        title="Python Developer",
        company="Stripe Inc",
        canonical_url="https://stripe.com/jobs/123?ref=greenhouse",
        location="Remote",
        remote_type="REMOTE",
        description="FastAPI role.",
    )
    score, reasons, conf = DuplicateDetectionService.compute_similarity(j1, j2)
    assert score == 1.0
    assert conf == DuplicateConfidence.HIGH_CONFIDENCE.value
    assert "Identical canonical URL" in reasons[0]


def test_similar_titles_different_employers_preserved():
    j1 = Job(
        id="j1",
        title="Senior Python Backend Engineer",
        company="Acme Corp",
        canonical_url="https://acme.example.com/jobs/1",
        location="Remote",
        remote_type="REMOTE",
        description="FastAPI backend engineer.",
    )
    j2 = Job(
        id="j2",
        title="Senior Python Backend Engineer",
        company="Globex Corp",
        canonical_url="https://globex.example.com/jobs/1",
        location="Remote",
        remote_type="REMOTE",
        description="FastAPI backend engineer.",
    )
    score, reasons, conf = DuplicateDetectionService.compute_similarity(j1, j2)
    assert conf == DuplicateConfidence.INSUFFICIENT_EVIDENCE.value
    assert score == 0.0


def test_distinct_physical_locations_prevent_false_merge():
    j1 = Job(
        id="j1",
        title="Software Engineer",
        company="TechCorp",
        canonical_url="https://tech.example.com/jobs/ny",
        location="New York, NY",
        remote_type="ON_SITE",
        description="On-site office development.",
    )
    j2 = Job(
        id="j2",
        title="Software Engineer",
        company="TechCorp",
        canonical_url="https://tech.example.com/jobs/sf",
        location="San Francisco, CA",
        remote_type="ON_SITE",
        description="On-site office development.",
    )
    score, reasons, conf = DuplicateDetectionService.compute_similarity(j1, j2)
    # Distinct physical offices indicate separate job requisitions
    assert conf != DuplicateConfidence.HIGH_CONFIDENCE.value
    assert score < 0.65


@pytest.mark.asyncio
async def test_duplicate_cluster_creation_and_review(db_session: AsyncSession):
    # Setup sources
    src1 = JobSource(identifier="source-a", name="Source A", base_url="https://a.example.com")
    src2 = JobSource(identifier="source-b", name="Source B", base_url="https://b.example.com")
    db_session.add_all([src1, src2])
    await db_session.flush()

    job1 = Job(
        source_id=src1.id,
        external_id="ext-101",
        title="Senior Platform Engineer",
        company="CloudScale Technologies",
        canonical_url="https://cloudscale.example.com/jobs/101",
        location="Remote",
        remote_type="REMOTE",
        description="Python, Kubernetes, Distributed Systems, Terraform.",
        first_seen_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    job2 = Job(
        source_id=src2.id,
        external_id="ext-202",
        title="Senior Platform Engineer",
        company="CloudScale",
        canonical_url="https://cloudscale.example.com/jobs/101?source=board2",
        location="Remote",
        remote_type="REMOTE",
        description="Python, Kubernetes, Distributed Systems, Terraform.",
        first_seen_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    db_session.add_all([job1, job2])
    await db_session.commit()

    # Cluster job2
    cluster = await DuplicateDetectionService.cluster_job(db_session, job2)
    assert cluster is not None
    assert cluster.cluster_status == ClusterStatus.DETECTED.value
    assert cluster.confidence == DuplicateConfidence.HIGH_CONFIDENCE.value
    # Canonical job should be job1 (seen earlier)
    assert cluster.canonical_job_id == job1.id
    assert job1.duplicate_cluster_id == cluster.id
    assert job2.duplicate_cluster_id == cluster.id

    # Review cluster - confirm
    updated = await DuplicateDetectionService.review_cluster(db_session, cluster.id, "CONFIRM", "Verified duplicate")
    assert updated.cluster_status == ClusterStatus.CONFIRMED.value
    assert updated.review_notes == "Verified duplicate"

    # Review cluster - dismiss
    dismissed = await DuplicateDetectionService.review_cluster(db_session, cluster.id, "DISMISS", "Keep distinct")
    assert dismissed.cluster_status == ClusterStatus.DISMISSED.value


@pytest.mark.asyncio
async def test_concurrent_duplicate_clustering_safety(db_session: AsyncSession):
    src = JobSource(identifier="source-c", name="Source C", base_url="https://c.example.com")
    db_session.add(src)
    await db_session.flush()

    job_base = Job(
        source_id=src.id,
        external_id="ext-c1",
        title="Lead Architect",
        company="Apex Systems",
        canonical_url="https://apex.example.com/jobs/arch",
        location="Remote",
        remote_type="REMOTE",
        description="Lead Python cloud architecture.",
    )
    job_dup1 = Job(
        source_id=src.id,
        external_id="ext-c2",
        title="Lead Architect",
        company="Apex Systems Inc",
        canonical_url="https://apex.example.com/jobs/arch?track=1",
        location="Remote",
        remote_type="REMOTE",
        description="Lead Python cloud architecture.",
    )
    job_dup2 = Job(
        source_id=src.id,
        external_id="ext-c3",
        title="Lead Architect",
        company="Apex Systems",
        canonical_url="https://apex.example.com/jobs/arch?track=2",
        location="Remote",
        remote_type="REMOTE",
        description="Lead Python cloud architecture.",
    )
    db_session.add_all([job_base, job_dup1, job_dup2])
    await db_session.commit()

    # Simulate sequential/concurrent cluster jobs
    c1 = await DuplicateDetectionService.cluster_job(db_session, job_dup1)
    c2 = await DuplicateDetectionService.cluster_job(db_session, job_dup2)

    assert c1 is not None
    assert c2 is not None
    # Both should join the same cluster
    assert c1.id == c2.id
    assert job_dup1.duplicate_cluster_id == c1.id
    assert job_dup2.duplicate_cluster_id == c1.id
