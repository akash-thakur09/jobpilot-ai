import hashlib
from pathlib import Path
from typing import Tuple
from fastapi import HTTPException, status
from backend.app.core.config import settings


class ResumeStorageService:
    """
    Manages immutable atomic storage, SHA-256 computation, and path traversal protection
    for generated job-specific resume PDFs.
    """

    @classmethod
    def save_resume_pdf(cls, pdf_bytes: bytes) -> Tuple[str, str]:
        """
        Saves PDF bytes atomically to disk if not already present.
        Returns:
            (file_path: str, file_sha256: str)
        """
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        filename = f"{sha256}.pdf"

        settings.RESUME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = settings.RESUME_STORAGE_DIR / filename

        # If file already exists with same hash, verify integrity and return
        if dest_path.exists():
            existing_hash = hashlib.sha256(dest_path.read_bytes()).hexdigest()
            if existing_hash == sha256:
                return str(dest_path), sha256

        # Atomic write using temp file
        temp_path = settings.RESUME_STORAGE_DIR / f"{sha256}.tmp"
        temp_path.write_bytes(pdf_bytes)
        temp_path.replace(dest_path)

        # Final disk verification
        saved_bytes = dest_path.read_bytes()
        verified_hash = hashlib.sha256(saved_bytes).hexdigest()
        if verified_hash != sha256:
            raise RuntimeError(
                f"Storage integrity failure: written file SHA-256 {verified_hash} != {sha256}"
            )

        return str(dest_path), sha256

    @classmethod
    def get_resume_pdf_path(cls, relative_or_absolute_path: str) -> Path:
        """
        Resolves and verifies that the file exists and is strictly within the allowed storage directory,
        preventing directory traversal attacks.
        """
        path = Path(relative_or_absolute_path).resolve()
        storage_root = settings.RESUME_STORAGE_DIR.resolve()

        # Path traversal guard
        try:
            path.relative_to(storage_root)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: invalid file path.",
            )

        if not path.exists() or not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume PDF file not found on disk.",
            )

        return path

    @classmethod
    def compute_sha256(cls, path: Path) -> str:
        """Computes SHA-256 checksum of file at path."""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def verify_file_integrity(cls, file_path_str: str, expected_sha256: str) -> bool:
        """Checks if the file exists and matches its recorded SHA-256 checksum."""
        try:
            path = cls.get_resume_pdf_path(file_path_str)
            computed = cls.compute_sha256(path)
            return computed == expected_sha256
        except Exception:
            return False

