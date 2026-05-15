from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
APP_DIR = BASE_DIR / "app"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
ENV_FILE = BASE_DIR / ".env"


def load_environment() -> None:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)


def normalize_database_url(database_url: str | None) -> str:
    if not database_url:
        database_url = "sqlite:///./db.db"

    if not database_url.startswith("sqlite"):
        return database_url

    scheme, separator, raw_path = database_url.partition(":///")
    if not separator or raw_path in {"", ":memory:"}:
        return database_url

    db_path = Path(raw_path)
    if db_path.is_absolute():
        return database_url

    absolute_path = (BASE_DIR / db_path).resolve()
    return f"{scheme}:///{absolute_path.as_posix()}"


def get_secret_key(default: str = "change-me-in-production") -> str:
    load_environment()
    return os.getenv("SECRET_KEY", default)
