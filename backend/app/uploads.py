"""File upload helpers with content-addressed deduplication."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import UploadFile

from .documents import sha256_file


def save_upload(upload: UploadFile, destination: Path) -> None:
    """Persist an uploaded file to *destination*, creating parent directories as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with destination.open("wb") as output:
        shutil.copyfileobj(upload.file, output)


def save_content_addressed_upload(upload: UploadFile, target_dir: Path, filename: str) -> Path:
    """Save an upload under a content-addressed (SHA-256) path to deduplicate identical files."""
    suffix = Path(filename).suffix.lower()
    incoming = target_dir / ".incoming"
    temporary_path = incoming / f"{os.urandom(12).hex()}{suffix}"
    save_upload(upload, temporary_path)
    try:
        digest = sha256_file(temporary_path)
        destination = target_dir / digest[:2] / f"{digest}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            temporary_path.unlink()
        else:
            temporary_path.replace(destination)
        return destination
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
