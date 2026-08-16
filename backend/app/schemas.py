from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ParagraphRead(BaseModel):
    id: str
    ordinal: int
    label: str
    text: str
    source_page_start: int
    source_page_end: int

    model_config = {"from_attributes": True}


class DocumentRead(BaseModel):
    id: str
    title: str
    neutral_citation: str | None
    court: str | None
    decision_date: date | None
    source_filename: str
    extraction_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnotationCreate(BaseModel):
    document_id: str
    paragraph_ids: list[str] = Field(min_length=1)
    proposition: str = Field(min_length=1, max_length=10000)
    # Nullable for reading annotations made before the decision-track migration.
    # New saves are required by the application validator to choose a track.
    decision_track: str | None = None
    bail_proceeding: str | None = None
    bail_issue: str | None = None
    bail_result: str | None = None
    bail_factors: list[str] = Field(default_factory=list)
    annotation_type: str
    areas: list[str] = Field(min_length=1)
    authority_weight: str
    function: str
    relationship_type: str | None = None
    boundary: str | None = None
    triggers: list[str] = Field(default_factory=list)
    commentary: str | None = None
    related_authorities: list[str] = Field(default_factory=list)


class AnnotationRead(AnnotationCreate):
    id: str
    ontology_version: str
    created_at: datetime
    updated_at: datetime


class AnnotationUpdate(AnnotationCreate):
    change_note: str | None = Field(default=None, max_length=1000)


class AnnotationRevisionRead(BaseModel):
    id: str
    revision_number: int
    snapshot_json: dict[str, object]
    change_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRead(BaseModel):
    filename: str
    bytes: int
    created_at: datetime


class StatuteSnapshotRead(BaseModel):
    id: str
    short_title: str
    citation: str
    jurisdiction: str
    language: str
    source_url: str
    current_to_date: date | None
    in_force_from: date | None
    in_force_to: date | None
    downloaded_at: datetime
    parser_version: str

    model_config = {"from_attributes": True}


class StatuteProvisionRead(BaseModel):
    id: str
    citation: str
    node_key: str | None
    parent_key: str | None
    kind: str
    heading: str | None
    marginal_note: str | None
    definition_term: str | None
    text: str
    parent_citation: str | None
    ordinal: int

    model_config = {"from_attributes": True}


class StatuteSectionPageRead(BaseModel):
    items: list[StatuteProvisionRead]
    total: int
    offset: int
    limit: int


class StatuteComparisonEntryRead(BaseModel):
    node_key: str
    citation: str
    label: str | None
    change: str
    earlier_text: str | None
    later_text: str | None


class StatuteComparisonRead(BaseModel):
    citation: str
    earlier_snapshot_id: str
    later_snapshot_id: str
    entries: list[StatuteComparisonEntryRead]
