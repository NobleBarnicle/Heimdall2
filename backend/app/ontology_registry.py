from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Annotation, OntologyValueMigration, OntologyVersion
from .ontology import load_ontology


def _register_legacy_versions(session: Session, current: dict[str, object]) -> None:
    """Make legacy labels visible without inventing a vocabulary we do not possess."""
    versions = set(session.scalars(select(Annotation.ontology_version).distinct()))
    for version in versions:
        if session.get(OntologyVersion, version):
            continue
        if version == current["version"]:
            continue
        session.add(
            OntologyVersion(
                version=version,
                snapshot_json={"version": version, "status": "historical snapshot unavailable"},
                fingerprint="historical-snapshot-unavailable",
                change_note="Registered after ontology history was introduced; the original vocabulary file is unavailable locally.",
            )
        )


def _register_current_version(session: Session, current: dict[str, object]) -> None:
    version = str(current["version"])
    existing = session.get(OntologyVersion, version)
    if not existing:
        session.add(
            OntologyVersion(
                version=version,
                snapshot_json=current["snapshot"],  # type: ignore[arg-type]
                fingerprint=str(current["fingerprint"]),
                change_note=str(current["change_note"]),
            )
        )
        return
    if existing.fingerprint != current["fingerprint"]:
        raise RuntimeError(
            f"ONTOLOGY.md changed after version {version} was registered. "
            "Increment the ontology version and add a Version History entry; registered versions are immutable."
        )


def _register_value_migrations(session: Session, current: dict[str, object]) -> None:
    for mapping in current["value_migrations"]:  # type: ignore[union-attr]
        existing = session.scalar(
            select(OntologyValueMigration).where(
                OntologyValueMigration.from_version == mapping["from_version"],
                OntologyValueMigration.to_version == mapping["to_version"],
                OntologyValueMigration.field == mapping["field"],
                OntologyValueMigration.previous_value == mapping["previous_value"],
            )
        )
        if existing:
            if existing.replacement_value != mapping["replacement_value"] or existing.reason != mapping["reason"]:
                raise RuntimeError("An existing ontology value migration cannot be edited; add a correcting migration instead.")
            continue
        session.add(
            OntologyValueMigration(
                from_version=mapping["from_version"],
                to_version=mapping["to_version"],
                field=mapping["field"],
                previous_value=mapping["previous_value"],
                replacement_value=mapping["replacement_value"],
                reason=mapping["reason"],
            )
        )


def synchronize_ontology_registry(session: Session) -> None:
    """Record the current ontology once and reject an in-place vocabulary rewrite."""
    current = load_ontology()
    _register_legacy_versions(session, current)
    _register_current_version(session, current)
    _register_value_migrations(session, current)
    session.commit()
