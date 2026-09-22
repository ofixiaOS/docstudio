from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class Settings:
    backend_dir: Path = BACKEND_DIR
    data_dir: Path = Path(os.getenv("GAMMA_DATA_DIR", BACKEND_DIR / "data")).resolve()
    library_root: Path = Path(
        os.getenv("STUDIO_LIBRARY_ROOT", os.getenv("DOCSTUDIO_LIBRARY_ROOT", str(BACKEND_DIR.parent.parent)))
    ).resolve()
    embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    embedding_dimensions: int = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768"))
    max_source_chars: int = int(os.getenv("GAMMA_MAX_SOURCE_CHARS", "120000"))

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    @property
    def default_author(self) -> str:
        return os.getenv("STUDIO_DEFAULT_AUTHOR", os.getenv("DEFAULT_STUDENT", "Nicolás Jara")).strip()

    @property
    def default_institution(self) -> str:
        return os.getenv("STUDIO_DEFAULT_INSTITUTION", os.getenv("DEFAULT_INSTITUTION", "")).strip()

    @property
    def default_career(self) -> str:
        return os.getenv("STUDIO_DEFAULT_CAREER", os.getenv("DEFAULT_CAREER", "")).strip()

    @property
    def database_path(self) -> Path:
        custom = os.getenv("DOCSTUDIO_DATABASE_PATH")
        if custom:
            return Path(custom).resolve()
        return self.data_dir / "docstudio.db"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.projects_dir.mkdir(parents=True, exist_ok=True)


def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def persist_env_value(name: str, value: str) -> None:
    """Update one key in .env without discarding unrelated settings."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated: list[str] = []
    found = False
    for line in lines:
        if line.startswith(f"{name}="):
            updated.append(f"{name}={value}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{name}={value}")
    ENV_FILE.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    os.environ[name] = value
