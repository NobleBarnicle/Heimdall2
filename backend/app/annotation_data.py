from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from .models import Annotation, AnnotationFacet, AnnotationParagraph, AnnotationRevision, Paragraph


FACET_FIELDS = {
    "area": "areas",
    "trigger": "triggers",
    "bail_factor": "bail_factors",
}


def annotation_snapshot(annotation: Annotation) -> dict[str, object]:
    """The human-approved state saved with every canonical revision."""
    return {
        "annotation_id": annotation.id,
        "document_id": annotation.document_id,
        "paragraph_ids": [link.paragraph_id for link in annotation.paragraph_links],
        "proposition": annotation.proposition,
        "decision_track": annotation.decision_track,
        "bail_proceeding": annotation.bail_proceeding,
        "bail_issue": annotation.bail_issue,
        "bail_result": annotation.bail_result,
        "bail_factors": annotation.bail_factors or [],
        "annotation_type": annotation.annotation_type,
        "areas": annotation.areas or [],
        "authority_weight": annotation.authority_weight,
        "function": annotation.function,
        "relationship_type": annotation.relationship_type,
        "boundary": annotation.boundary,
        "triggers": annotation.triggers or [],
        "commentary": annotation.commentary,
        "related_authorities": annotation.related_authorities or [],
        "ontology_version": annotation.ontology_version,
        "deleted_at": annotation.deleted_at.isoformat() if annotation.deleted_at else None,
    }


def _sync_facets(session: Session, annotation: Annotation) -> None:
    session.execute(delete(AnnotationFacet).where(AnnotationFacet.annotation_id == annotation.id))
    for facet_type, attribute in FACET_FIELDS.items():
        for value in getattr(annotation, attribute) or []:
            session.add(AnnotationFacet(annotation_id=annotation.id, facet_type=facet_type, value=value))


def _sync_search(session: Session, annotation: Annotation) -> None:
    session.execute(text("DELETE FROM annotation_search WHERE annotation_id = :annotation_id"), {"annotation_id": annotation.id})
    if annotation.deleted_at:
        return
    paragraph_text = "\n".join(
        session.scalars(
            select(Paragraph.text)
            .join(AnnotationParagraph, AnnotationParagraph.paragraph_id == Paragraph.id)
            .where(AnnotationParagraph.annotation_id == annotation.id)
            .order_by(Paragraph.ordinal)
        )
    )
    session.execute(
        text(
            "INSERT INTO annotation_search (annotation_id, proposition, commentary, paragraph_text) "
            "VALUES (:annotation_id, :proposition, :commentary, :paragraph_text)"
        ),
        {
            "annotation_id": annotation.id,
            "proposition": annotation.proposition,
            "commentary": annotation.commentary or "",
            "paragraph_text": paragraph_text,
        },
    )


def record_revision(session: Session, annotation: Annotation, change_note: str | None) -> AnnotationRevision:
    next_number = (session.scalar(select(func.max(AnnotationRevision.revision_number)).where(AnnotationRevision.annotation_id == annotation.id)) or 0) + 1
    revision = AnnotationRevision(
        annotation_id=annotation.id,
        revision_number=next_number,
        snapshot_json=annotation_snapshot(annotation),
        change_note=change_note.strip() if change_note else None,
    )
    session.add(revision)
    return revision


def synchronize_annotation(session: Session, annotation: Annotation, change_note: str | None) -> None:
    """Update derived indexes and append a canonical revision in the same transaction."""
    _sync_facets(session, annotation)
    _sync_search(session, annotation)
    record_revision(session, annotation, change_note)


def rebuild_annotation_data(session: Session) -> None:
    """Backfill new derived structures without changing any human-authored annotation."""
    session.execute(text("DELETE FROM annotation_search"))
    annotations = list(session.scalars(select(Annotation)))
    for annotation in annotations:
        _sync_facets(session, annotation)
        _sync_search(session, annotation)
        if not session.scalar(select(AnnotationRevision.id).where(AnnotationRevision.annotation_id == annotation.id).limit(1)):
            record_revision(session, annotation, "Initial history created during data-foundation migration")
    session.commit()


def fts_query(query: str) -> str:
    """Turn free-form input into an AND search without exposing FTS operators."""
    terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
    return " ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def matching_annotation_ids(session: Session, query: str) -> list[str]:
    match = fts_query(query)
    if not match:
        return []
    return list(
        session.execute(text("SELECT annotation_id FROM annotation_search WHERE annotation_search MATCH :query"), {"query": match}).scalars()
    )
