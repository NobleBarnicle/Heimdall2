from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Document, DocumentFacet


FACET_FIELDS = {
    "bail_ground": "bail_grounds",
    "bail_case_material": "bail_case_material",
}


def synchronize_document_facets(session: Session, document: Document) -> None:
    """Keep case-profile filters aligned with the document's canonical values."""
    session.execute(delete(DocumentFacet).where(DocumentFacet.document_id == document.id))
    for facet_type, attribute in FACET_FIELDS.items():
        for value in getattr(document, attribute) or []:
            session.add(DocumentFacet(document_id=document.id, facet_type=facet_type, value=value))


def rebuild_document_facets(session: Session) -> None:
    session.execute(delete(DocumentFacet))
    for document in session.scalars(select(Document)):
        synchronize_document_facets(session, document)
    session.commit()
