from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_PATH, ensure_data_directories

ensure_data_directories()
engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def ensure_schema() -> None:
    """Create new tables and apply small, backwards-compatible local migrations."""
    Base.metadata.create_all(bind=engine)
    additions = {
        "annotations": {
            "decision_track": "VARCHAR",
            "bail_proceeding": "VARCHAR",
            "bail_issue": "VARCHAR",
            "bail_result": "VARCHAR",
            "bail_factors": "JSON",
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
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, column_type in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))


def get_session():
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
