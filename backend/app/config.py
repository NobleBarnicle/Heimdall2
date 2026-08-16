from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    configured = os.getenv("HEIMDALL_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Library" / "Application Support" / "Heimdall").resolve()


DATA_DIR = data_dir()
DATABASE_PATH = DATA_DIR / "heimdall.sqlite3"
DOCUMENTS_DIR = DATA_DIR / "documents"
STATUTES_DIR = DATA_DIR / "statutes"
EXPORTS_DIR = DATA_DIR / "exports"
BACKUPS_DIR = DATA_DIR / "backups"


def ensure_data_directories() -> None:
    for directory in (DATA_DIR, DOCUMENTS_DIR, STATUTES_DIR, EXPORTS_DIR, BACKUPS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
