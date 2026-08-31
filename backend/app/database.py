from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import BACKUPS_DIR, DATABASE_PATH, ensure_data_directories

ensure_data_directories()
engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def _add_missing_columns(connection: Connection) -> None:
    """Bridge databases created before migrations were introduced."""
    additions = {
        "annotations": {
            "decision_track": "VARCHAR",
            "bail_proceeding": "VARCHAR",
            "bail_issue": "VARCHAR",
            "bail_result": "VARCHAR",
            "bail_factors": "JSON",
        },
        "documents": {
            "bail_proceeding": "VARCHAR",
            "bail_result": "VARCHAR",
            "bail_grounds": "JSON",
            "bail_case_material": "JSON",
            "bail_case_note": "TEXT",
        },
        "statute_snapshots": {
            "in_force_from": "DATE",
            "in_force_to": "DATE",
        },
        "statute_provisions": {
            "node_key": "VARCHAR",
            "parent_key": "VARCHAR",
            "definition_term": "VARCHAR",
        },
    }
    inspector = inspect(connection)
    for table, columns in additions.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, column_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))
    document_columns = {column["name"] for column in inspect(connection).get_columns("documents")}
    if {"bail_grounds", "bail_case_material"}.issubset(document_columns):
        connection.execute(text("UPDATE documents SET bail_grounds = '[]' WHERE bail_grounds IS NULL"))
        connection.execute(text("UPDATE documents SET bail_case_material = '[]' WHERE bail_case_material IS NULL"))


def _add_annotation_indexes(connection: Connection) -> None:
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_annotations_active_updated ON annotations (deleted_at, updated_at)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_annotation_facets_lookup ON annotation_facets (facet_type, value, annotation_id)"))
    connection.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS annotation_search "
            "USING fts5(annotation_id UNINDEXED, proposition, commentary, paragraph_text)"
        )
    )


def _add_document_facet_indexes(connection: Connection) -> None:
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_document_facets_lookup ON document_facets (facet_type, value, document_id)"))


def _add_ontology_registry_indexes(connection: Connection) -> None:
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_ontology_value_migrations_lookup "
            "ON ontology_value_migrations (field, previous_value, from_version, to_version)"
        )
    )


MIGRATIONS: tuple[tuple[str, Callable[[Connection], None]], ...] = (
    ("0001_legacy_columns", _add_missing_columns),
    ("0002_annotation_foundation", _add_annotation_indexes),
    ("0003_ontology_registry", _add_ontology_registry_indexes),
    ("0004_document_bail_context", _add_missing_columns),
    ("0005_bail_case_profile", _add_missing_columns),
    ("0006_document_facets", _add_document_facet_indexes),
)


def create_backup(label: str = "manual") -> Path:
    """Create a consistent SQLite backup without copying a live database file directly."""
    ensure_data_directories()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = BACKUPS_DIR / f"heimdall-{label}-{timestamp}.sqlite3"
    with sqlite3.connect(str(DATABASE_PATH)) as source, sqlite3.connect(str(destination)) as target:
        source.backup(target)
    return destination


def ensure_schema() -> None:
    """Apply recorded, forward-only local migrations and protect existing data first."""
    database_existed = DATABASE_PATH.exists()
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
        )
        applied = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
    pending = [(version, migration) for version, migration in MIGRATIONS if version not in applied]
    if database_existed and pending:
        create_backup("before-migration")
    with engine.begin() as connection:
        for version, migration in pending:
            migration(connection)
            connection.execute(
                text("INSERT INTO schema_migrations (version, applied_at) VALUES (:version, :applied_at)"),
                {"version": version, "applied_at": datetime.now(timezone.utc).isoformat()},
            )


def get_session():
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
