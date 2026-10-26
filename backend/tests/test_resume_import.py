import io
import pytest
from httpx import AsyncClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import pypdf


def create_sample_pdf(text_lines: list[str]) -> bytes:
    """Helper to generate an in-memory PDF with text lines."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in text_lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_valid_resume_and_confirm(client: AsyncClient):
    pdf_bytes = create_sample_pdf([
        "Marcus Vance",
        "marcus.vance@example.org | (555) 234-5678 | San Francisco, CA",
        "Senior Cloud Architect with extensive experience in distributed systems.",
        "Skills: Python, Kubernetes, Docker, AWS, PostgreSQL, Terraform",
        "Experience:",
        "Staff Architect at Apex Cloud Solutions (2019 - Present)",
        "- Designed serverless multi-tenant platform",
    ])

    files = {"file": ("marcus_resume.pdf", pdf_bytes, "application/pdf")}
    res = await client.post("/api/v1/profile/import-resume", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["original_filename"] == "marcus_resume.pdf"
    assert data["file_sha256"] is not None
    assert data["requires_confirmation"] is True
    assert "Marcus Vance" in data["draft_profile"]["full_name"]
    assert "marcus.vance@example.org" in data["draft_profile"]["email"]

    # Verify detected skills are marked unverified in the draft
    skills = data["draft_profile"]["skills"]
    skill_names = [s["skill_name"] for s in skills]
    assert "Python" in skill_names
    assert "Kubernetes" in skill_names
    assert "AWS" in skill_names
    for s in skills:
        assert s["is_verified"] is False

    # Now confirm the draft profile into the actual profile
    confirm_payload = {
        "file_sha256": data["file_sha256"],
        "confirmed_profile": {
            **data["draft_profile"],
            "location": "San Francisco, CA",
            "work_authorization": "US Citizen",
            "years_of_experience": 8.0,
            "target_titles": ["Staff Cloud Architect"],
        },
    }
    confirm_res = await client.post("/api/v1/profile/import-resume/confirm", json=confirm_payload)
    assert confirm_res.status_code == 201
    profile = confirm_res.json()
    assert profile["full_name"] == "Marcus Vance"
    assert profile["email"] == "marcus.vance@example.org"
    assert len(profile["skills"]) > 0
    # Verified that upon confirmation, skills are marked is_verified=True
    assert all(s["is_verified"] is True for s in profile["skills"])


@pytest.mark.asyncio
async def test_import_empty_file_rejected(client: AsyncClient):
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    res = await client.post("/api/v1/profile/import-resume", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_non_pdf_rejected(client: AsyncClient):
    files = {"file": ("resume.docx", b"some word content", "application/vnd.openxmlformats")}
    res = await client.post("/api/v1/profile/import-resume", files=files)
    assert res.status_code == 400
    assert "pdf" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_corrupted_pdf_rejected(client: AsyncClient):
    files = {"file": ("corrupt.pdf", b"%PDF-1.4 completely broken content not a valid pdf %%EOF", "application/pdf")}
    res = await client.post("/api/v1/profile/import-resume", files=files)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_import_blank_pdf_rejected(client: AsyncClient):
    # PDF with canvas but zero text
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.showPage()
    c.save()
    blank_bytes = buf.getvalue()

    files = {"file": ("blank.pdf", blank_bytes, "application/pdf")}
    res = await client.post("/api/v1/profile/import-resume", files=files)
    assert res.status_code == 422
    assert "no readable text" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_encrypted_pdf_rejected(client: AsyncClient):
    # Generate encrypted PDF
    sample = create_sample_pdf(["Confidential text"])
    reader = pypdf.PdfReader(io.BytesIO(sample))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret_password")

    enc_buf = io.BytesIO()
    writer.write(enc_buf)
    encrypted_bytes = enc_buf.getvalue()

    files = {"file": ("locked.pdf", encrypted_bytes, "application/pdf")}
    res = await client.post("/api/v1/profile/import-resume", files=files)
    assert res.status_code == 422
    assert "encrypted" in res.json()["detail"].lower()
