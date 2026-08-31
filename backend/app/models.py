from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String, index=True)
    neutral_citation: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    court: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decision_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_filename: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String, unique=True)
    sha256: Mapped[str] = mapped_column(String, index=True)
    extraction_status: Mapped[str] = mapped_column(String, default="pending")
    # Case-level Bail context.  Bail annotations inherit these values when saved.
    bail_proceeding: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bail_result: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Case-level Bail profile. Grounds describe legal scope; material describes
    # facts and context present in the case.
    bail_grounds: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True, default=list)
    bail_case_material: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True, default=list)
    bail_case_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    paragraphs: Mapped[list[Paragraph]] = relationship(back_populates="document", cascade="all, delete-orphan")
    annotations: Mapped[list[Annotation]] = relationship(back_populates="document", cascade="all, delete-orphan")
    facets: Mapped[list[DocumentFacet]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    source_page_start: Mapped[int] = mapped_column(Integer)
    source_page_end: Mapped[int] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="paragraphs")
    annotation_links: Mapped[list[AnnotationParagraph]] = relationship(back_populates="paragraph")


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    proposition: Mapped[str] = mapped_column(Text)
    decision_track: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bail_proceeding: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bail_issue: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bail_result: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bail_factors: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True, default=list)
    annotation_type: Mapped[str] = mapped_column(String)
    areas: Mapped[list[str]] = mapped_column(JSON)
    authority_weight: Mapped[str] = mapped_column(String)
    function: Mapped[str] = mapped_column(String)
    relationship_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    boundary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    triggers: Mapped[list[str]] = mapped_column(JSON, default=list)
    commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_authorities: Mapped[list[str]] = mapped_column(JSON, default=list)
    ontology_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship(back_populates="annotations")
    paragraph_links: Mapped[list[AnnotationParagraph]] = relationship(back_populates="annotation", cascade="all, delete-orphan")
    revisions: Mapped[list[AnnotationRevision]] = relationship(back_populates="annotation", cascade="all, delete-orphan")
    facets: Mapped[list[AnnotationFacet]] = relationship(back_populates="annotation", cascade="all, delete-orphan")


class AnnotationParagraph(Base):
    __tablename__ = "annotation_paragraphs"

    annotation_id: Mapped[str] = mapped_column(ForeignKey("annotations.id"), primary_key=True)
    paragraph_id: Mapped[str] = mapped_column(ForeignKey("paragraphs.id"), primary_key=True)
    annotation: Mapped[Annotation] = relationship(back_populates="paragraph_links")
    paragraph: Mapped[Paragraph] = relationship(back_populates="annotation_links")


class AnnotationRevision(Base):
    __tablename__ = "annotation_revisions"
    __table_args__ = (UniqueConstraint("annotation_id", "revision_number", name="uq_annotation_revision_number"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    annotation_id: Mapped[str] = mapped_column(ForeignKey("annotations.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    annotation: Mapped[Annotation] = relationship(back_populates="revisions")


class AnnotationFacet(Base):
    """Normalized, queryable values for annotations that may have more than one value."""

    __tablename__ = "annotation_facets"

    annotation_id: Mapped[str] = mapped_column(ForeignKey("annotations.id"), primary_key=True)
    facet_type: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, primary_key=True, index=True)

    annotation: Mapped[Annotation] = relationship(back_populates="facets")


class DocumentFacet(Base):
    """Normalized, queryable case-level Bail profile values."""

    __tablename__ = "document_facets"

    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    facet_type: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, primary_key=True, index=True)

    document: Mapped[Document] = relationship(back_populates="facets")


class OntologyVersion(Base):
    """An immutable local copy of the vocabulary used by annotations."""

    __tablename__ = "ontology_versions"

    version: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String)
    change_note: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OntologyValueMigration(Base):
    """A documented cross-version meaning map; it never mutates annotations automatically."""

    __tablename__ = "ontology_value_migrations"
    __table_args__ = (
        UniqueConstraint("from_version", "to_version", "field", "previous_value", name="uq_ontology_value_migration"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    from_version: Mapped[str] = mapped_column(String, index=True)
    to_version: Mapped[str] = mapped_column(String, index=True)
    field: Mapped[str] = mapped_column(String)
    previous_value: Mapped[str] = mapped_column(String)
    replacement_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class StatuteSnapshot(Base):
    __tablename__ = "statute_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    short_title: Mapped[str] = mapped_column(String)
    citation: Mapped[str] = mapped_column(String)
    jurisdiction: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    source_format: Mapped[str] = mapped_column(String)
    source_sha256: Mapped[str] = mapped_column(String)
    current_to_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    in_force_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    in_force_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    parser_version: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)
    provisions: Mapped[list[StatuteProvision]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class StatuteProvision(Base):
    __tablename__ = "statute_provisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("statute_snapshots.id"), index=True)
    citation: Mapped[str] = mapped_column(String, index=True)
    node_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    parent_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String)
    heading: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    marginal_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    definition_term: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    parent_citation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer)

    snapshot: Mapped[StatuteSnapshot] = relationship(back_populates="provisions")
