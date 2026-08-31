from __future__ import annotations

import hashlib
import json
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .annotation_data import matching_annotation_ids, rebuild_annotation_data, synchronize_annotation
from .document_data import rebuild_document_facets, synchronize_document_facets
from .config import BACKUPS_DIR, DOCUMENTS_DIR
from .database import SessionLocal, create_backup, ensure_schema, get_session
from .extraction import extract_paragraphs
from .models import Annotation, AnnotationFacet, AnnotationParagraph, AnnotationRevision, Document, DocumentFacet, OntologyValueMigration, OntologyVersion, Paragraph, StatuteProvision, StatuteSnapshot
from .ontology import load_ontology, requires_commentary, validate_values
from .ontology_registry import synchronize_ontology_registry
from .schemas import AnnotationCreate, AnnotationRead, AnnotationRevisionRead, AnnotationUpdate, BackupRead, DocumentCaseContextUpdate, DocumentRead, OntologyValueMigrationRead, OntologyVersionRead, ParagraphRead, StatuteComparisonRead, StatuteProvisionRead, StatuteSectionPageRead, StatuteSnapshotRead
from .statutes import compare_snapshots, import_criminal_code, import_criminal_code_at, refresh_legacy_snapshot


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema()
    with SessionLocal() as session:
        synchronize_ontology_registry(session)
        rebuild_annotation_data(session)
        rebuild_document_facets(session)
    yield


app = FastAPI(title="Heimdall", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ontology")
def ontology() -> dict[str, object]:
    return load_ontology()


@app.get("/api/ontology/versions", response_model=list[OntologyVersionRead])
def list_ontology_versions(session: Session = Depends(get_session)) -> list[OntologyVersion]:
    return list(session.scalars(select(OntologyVersion).order_by(OntologyVersion.recorded_at.desc())))


@app.get("/api/ontology/versions/{version}", response_model=OntologyVersionRead)
def get_ontology_version(version: str, session: Session = Depends(get_session)) -> OntologyVersion:
    ontology_version = session.get(OntologyVersion, version)
    if not ontology_version:
        raise HTTPException(status_code=404, detail="Ontology version not found")
    return ontology_version


@app.get("/api/ontology/value-migrations", response_model=list[OntologyValueMigrationRead])
def list_ontology_value_migrations(session: Session = Depends(get_session)) -> list[OntologyValueMigration]:
    return list(
        session.scalars(
            select(OntologyValueMigration).order_by(
                OntologyValueMigration.from_version, OntologyValueMigration.to_version, OntologyValueMigration.field
            )
        )
    )


@app.post("/api/documents", response_model=DocumentRead, status_code=201)
async def import_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    neutral_citation: str | None = Form(None),
    court: str | None = Form(None),
    decision_date: date | None = Form(None),
    session: Session = Depends(get_session),
) -> Document:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files can be imported")
    contents = await file.read()
    if not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid PDF")

    document_id = str(uuid4())
    document_directory = DOCUMENTS_DIR / document_id
    document_directory.mkdir(parents=True, exist_ok=False)
    destination = document_directory / "original.pdf"
    destination.write_bytes(contents)
    document = Document(
        id=document_id,
        title=title.strip(),
        neutral_citation=neutral_citation.strip() if neutral_citation else None,
        court=court.strip() if court else None,
        decision_date=decision_date,
        source_filename=Path(file.filename).name,
        stored_path=str(destination.relative_to(DOCUMENTS_DIR.parent)),
        sha256=hashlib.sha256(contents).hexdigest(),
        extraction_status="extracting",
    )
    session.add(document)
    try:
        extracted = extract_paragraphs(destination)
        for ordinal, paragraph in enumerate(extracted, start=1):
            session.add(Paragraph(document_id=document.id, ordinal=ordinal, **paragraph))
        document.extraction_status = "complete" if extracted else "empty"
        session.commit()
    except Exception as exc:
        session.rollback()
        destination.unlink(missing_ok=True)
        document_directory.rmdir()
        raise HTTPException(status_code=422, detail=f"Could not extract text from PDF: {exc}") from exc
    session.refresh(document)
    return document


@app.get("/api/documents", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    return list(session.scalars(select(Document).order_by(Document.created_at.desc())))


@app.get("/api/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, session: Session = Depends(get_session)) -> Document:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.patch("/api/documents/{document_id}/case-context", response_model=DocumentRead)
def update_document_case_context(
    document_id: str,
    payload: DocumentCaseContextUpdate,
    session: Session = Depends(get_session),
) -> Document:
    """Save the shared Bail profile and keep inherited annotation context aligned."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        validate_values("Bail Proceeding", [payload.bail_proceeding])
        validate_values("Bail Result", [payload.bail_result])
        validate_values("Bail Grounds", payload.bail_grounds)
        validate_values("Bail Case Material", payload.bail_case_material)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    document.bail_proceeding = payload.bail_proceeding
    document.bail_result = payload.bail_result
    document.bail_grounds = list(dict.fromkeys(payload.bail_grounds))
    document.bail_case_material = list(dict.fromkeys(payload.bail_case_material))
    document.bail_case_note = payload.bail_case_note.strip() if payload.bail_case_note else None
    if "Other" in document.bail_case_material and not document.bail_case_note:
        raise HTTPException(status_code=422, detail="Case note is required when using Other case-specific material")
    synchronize_document_facets(session, document)
    existing_annotations = list(
        session.scalars(
            select(Annotation)
            .where(Annotation.document_id == document.id, Annotation.decision_track == "Bail", Annotation.deleted_at.is_(None))
            .options(selectinload(Annotation.paragraph_links))
        )
    )
    for annotation in existing_annotations:
        annotation.bail_proceeding = payload.bail_proceeding
        annotation.bail_result = payload.bail_result
        synchronize_annotation(session, annotation, "Updated inherited case context")
    session.commit()
    session.refresh(document)
    return document


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: str, session: Session = Depends(get_session)) -> FileResponse:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    source = DOCUMENTS_DIR.parent / document.stored_path
    if not source.exists():
        raise HTTPException(status_code=404, detail="Stored PDF is missing")
    return FileResponse(
        source,
        media_type="application/pdf",
        filename=document.source_filename,
        content_disposition_type="inline",
    )


@app.get("/api/documents/{document_id}/paragraphs", response_model=list[ParagraphRead])
def list_paragraphs(document_id: str, session: Session = Depends(get_session)) -> list[Paragraph]:
    if not session.get(Document, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return list(session.scalars(select(Paragraph).where(Paragraph.document_id == document_id).order_by(Paragraph.ordinal)))


@app.post("/api/documents/{document_id}/paragraphs/reextract", response_model=list[ParagraphRead])
def reextract_paragraphs(document_id: str, session: Session = Depends(get_session)) -> list[Paragraph]:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if session.scalar(select(Annotation.id).where(Annotation.document_id == document_id).limit(1)):
        raise HTTPException(
            status_code=409,
            detail="This judgment has annotations. Re-extraction is blocked to protect paragraph provenance.",
        )
    source = DOCUMENTS_DIR.parent / document.stored_path
    if not source.exists():
        raise HTTPException(status_code=404, detail="Stored PDF is missing")
    try:
        extracted = extract_paragraphs(source)
        session.execute(delete(Paragraph).where(Paragraph.document_id == document_id))
        for ordinal, paragraph in enumerate(extracted, start=1):
            session.add(Paragraph(document_id=document.id, ordinal=ordinal, **paragraph))
        document.extraction_status = "complete" if extracted else "empty"
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=f"Could not re-extract text from PDF: {exc}") from exc
    return list(session.scalars(select(Paragraph).where(Paragraph.document_id == document_id).order_by(Paragraph.ordinal)))


def _validate_annotation(payload: AnnotationCreate, session: Session, document: Document) -> None:
    if not payload.decision_track:
        raise HTTPException(status_code=422, detail="Choose a research track")
    try:
        validate_values("Research Track", [payload.decision_track])
        validate_values("Type", [payload.annotation_type])
        validate_values("Area", payload.areas)
        validate_values("Authority Weight", [payload.authority_weight])
        validate_values("Function", [payload.function])
        if payload.relationship_type:
            validate_values("Relationship", [payload.relationship_type])
        if payload.boundary:
            validate_values("Boundary", [payload.boundary])
        validate_values("Trigger", payload.triggers)
        if payload.decision_track == "Bail":
            if not all([document.bail_proceeding, document.bail_result]):
                raise ValueError("Set the Bail case context (proceeding and result) before saving Bail annotations")
            if not payload.bail_issue:
                raise ValueError("Bail annotations require a main issue")
            if payload.bail_proceeding and payload.bail_proceeding != document.bail_proceeding:
                raise ValueError("Bail proceeding must match the saved case context")
            if payload.bail_result and payload.bail_result != document.bail_result:
                raise ValueError("Bail result must match the saved case context")
            validate_values("Bail Proceeding", [document.bail_proceeding])
            validate_values("Bail Issue", [payload.bail_issue])
            validate_values("Bail Result", [document.bail_result])
        elif any([payload.bail_proceeding, payload.bail_issue, payload.bail_result]):
            raise ValueError("Bail details can only be used with the Bail research track")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    all_values = [payload.decision_track, payload.annotation_type, *payload.areas, payload.authority_weight, payload.function, *payload.triggers]
    all_values.extend(value for value in [payload.bail_proceeding, payload.bail_issue, payload.bail_result] if value)
    if payload.decision_track == "Bail":
        all_values.extend([document.bail_proceeding, document.bail_result])
    if payload.relationship_type:
        all_values.append(payload.relationship_type)
    if payload.boundary:
        all_values.append(payload.boundary)
    if requires_commentary(all_values) and not payload.commentary:
        raise HTTPException(status_code=422, detail="Commentary is required when using Other")
    if payload.relationship_type and not payload.related_authorities:
        raise HTTPException(status_code=422, detail="A relationship requires a related authority")
    paragraphs = list(session.scalars(select(Paragraph).where(Paragraph.id.in_(payload.paragraph_ids))))
    if len(paragraphs) != len(set(payload.paragraph_ids)) or any(item.document_id != payload.document_id for item in paragraphs):
        raise HTTPException(status_code=422, detail="Paragraphs must belong to the selected document")
    if any(item.label == "heading" for item in paragraphs):
        raise HTTPException(status_code=422, detail="Section headings cannot be used as proposition provenance")


def _annotation_read(annotation: Annotation) -> AnnotationRead:
    return AnnotationRead(
        id=annotation.id,
        document_id=annotation.document_id,
        paragraph_ids=[link.paragraph_id for link in annotation.paragraph_links],
        proposition=annotation.proposition,
        decision_track=annotation.decision_track,
        bail_proceeding=annotation.bail_proceeding,
        bail_issue=annotation.bail_issue,
        bail_result=annotation.bail_result,
        annotation_type=annotation.annotation_type,
        areas=annotation.areas,
        authority_weight=annotation.authority_weight,
        function=annotation.function,
        relationship_type=annotation.relationship_type,
        boundary=annotation.boundary,
        triggers=annotation.triggers,
        commentary=annotation.commentary,
        related_authorities=annotation.related_authorities,
        ontology_version=annotation.ontology_version,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


def _add_ground_from_bail_issue(session: Session, document: Document, bail_issue: str | None) -> None:
    """A saved ground proposition is conclusive evidence that the ground is in issue."""
    if bail_issue not in {"Primary ground", "Secondary ground", "Tertiary ground"}:
        return
    grounds = document.bail_grounds or []
    if bail_issue not in grounds:
        document.bail_grounds = [*grounds, bail_issue]
        synchronize_document_facets(session, document)


@app.post("/api/annotations", response_model=AnnotationRead, status_code=201)
def create_annotation(payload: AnnotationCreate, session: Session = Depends(get_session)) -> AnnotationRead:
    document = session.get(Document, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    _validate_annotation(payload, session, document)
    if payload.decision_track == "Bail":
        _add_ground_from_bail_issue(session, document, payload.bail_issue)
    annotation = Annotation(
        document_id=payload.document_id,
        proposition=payload.proposition.strip(),
        decision_track=payload.decision_track,
        bail_proceeding=document.bail_proceeding if payload.decision_track == "Bail" else None,
        bail_issue=payload.bail_issue,
        bail_result=document.bail_result if payload.decision_track == "Bail" else None,
        # Retained as an empty legacy column so historic annotations remain readable.
        bail_factors=[],
        annotation_type=payload.annotation_type,
        areas=payload.areas,
        authority_weight=payload.authority_weight,
        function=payload.function,
        relationship_type=payload.relationship_type,
        boundary=payload.boundary,
        triggers=payload.triggers,
        commentary=payload.commentary.strip() if payload.commentary else None,
        related_authorities=payload.related_authorities,
        ontology_version=str(load_ontology()["version"]),
    )
    session.add(annotation)
    session.flush()
    for paragraph_id in payload.paragraph_ids:
        session.add(AnnotationParagraph(annotation_id=annotation.id, paragraph_id=paragraph_id))
    session.flush()
    synchronize_annotation(session, annotation, "Created")
    session.commit()
    annotation = session.scalar(
        select(Annotation).where(Annotation.id == annotation.id).options(selectinload(Annotation.paragraph_links))
    )
    return _annotation_read(annotation)


@app.patch("/api/annotations/{annotation_id}", response_model=AnnotationRead)
def update_annotation(annotation_id: str, payload: AnnotationUpdate, session: Session = Depends(get_session)) -> AnnotationRead:
    annotation = session.scalar(
        select(Annotation).where(Annotation.id == annotation_id, Annotation.deleted_at.is_(None)).options(selectinload(Annotation.paragraph_links))
    )
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    if annotation.document_id != payload.document_id:
        raise HTTPException(status_code=422, detail="An annotation cannot be moved to a different judgment")
    document = session.get(Document, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    _validate_annotation(payload, session, document)
    for field in (
        "proposition", "decision_track", "bail_proceeding", "bail_issue", "bail_result",
        "annotation_type", "areas", "authority_weight", "function", "relationship_type", "boundary",
        "triggers", "commentary", "related_authorities",
    ):
        value = getattr(payload, field)
        if field == "bail_proceeding" and payload.decision_track == "Bail":
            value = document.bail_proceeding
        if field == "bail_result" and payload.decision_track == "Bail":
            value = document.bail_result
        if field == "proposition" and isinstance(value, str):
            value = value.strip()
        if field == "commentary" and isinstance(value, str):
            value = value.strip() or None
        setattr(annotation, field, value)
    annotation.ontology_version = str(load_ontology()["version"])
    if payload.decision_track == "Bail":
        _add_ground_from_bail_issue(session, document, payload.bail_issue)
    session.execute(delete(AnnotationParagraph).where(AnnotationParagraph.annotation_id == annotation.id))
    for paragraph_id in payload.paragraph_ids:
        session.add(AnnotationParagraph(annotation_id=annotation.id, paragraph_id=paragraph_id))
    session.flush()
    synchronize_annotation(session, annotation, payload.change_note or "Updated")
    session.commit()
    annotation = session.scalar(
        select(Annotation).where(Annotation.id == annotation.id).options(selectinload(Annotation.paragraph_links))
    )
    return _annotation_read(annotation)


@app.get("/api/annotations/{annotation_id}/revisions", response_model=list[AnnotationRevisionRead])
def list_annotation_revisions(annotation_id: str, session: Session = Depends(get_session)) -> list[AnnotationRevision]:
    if not session.get(Annotation, annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found")
    return list(session.scalars(select(AnnotationRevision).where(AnnotationRevision.annotation_id == annotation_id).order_by(AnnotationRevision.revision_number.desc())))


@app.delete("/api/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: str, session: Session = Depends(get_session)) -> None:
    annotation = session.scalar(
        select(Annotation).where(Annotation.id == annotation_id, Annotation.deleted_at.is_(None)).options(selectinload(Annotation.paragraph_links))
    )
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    annotation.deleted_at = datetime.now(timezone.utc)
    session.flush()
    synchronize_annotation(session, annotation, "Deleted")
    session.commit()


@app.get("/api/annotations", response_model=list[AnnotationRead])
def search_annotations(
    q: str | None = Query(None),
    area: str | None = Query(None),
    annotation_type: str | None = Query(None),
    bail_proceeding: str | None = Query(None),
    bail_result: str | None = Query(None),
    bail_ground: list[str] = Query(default=[]),
    bail_case_material: list[str] = Query(default=[]),
    trigger: list[str] = Query(default=[]),
    session: Session = Depends(get_session),
) -> list[AnnotationRead]:
    statement = select(Annotation).where(Annotation.deleted_at.is_(None)).options(selectinload(Annotation.paragraph_links))
    if q:
        matching_ids = matching_annotation_ids(session, q)
        if not matching_ids:
            return []
        statement = statement.where(Annotation.id.in_(matching_ids))
    if annotation_type:
        statement = statement.where(Annotation.annotation_type == annotation_type)
    if bail_proceeding:
        statement = statement.where(Annotation.bail_proceeding == bail_proceeding)
    if bail_result:
        statement = statement.where(Annotation.bail_result == bail_result)
    if area:
        statement = statement.where(
            Annotation.id.in_(
                select(AnnotationFacet.annotation_id).where(AnnotationFacet.facet_type == "area", AnnotationFacet.value == area)
            )
        )
    for ground in bail_ground:
        statement = statement.where(
            Annotation.document_id.in_(
                select(DocumentFacet.document_id).where(DocumentFacet.facet_type == "bail_ground", DocumentFacet.value == ground)
            )
        )
    for material in bail_case_material:
        statement = statement.where(
            Annotation.document_id.in_(
                select(DocumentFacet.document_id).where(
                    DocumentFacet.facet_type == "bail_case_material", DocumentFacet.value == material
                )
            )
        )
    for trigger_value in trigger:
        statement = statement.where(
            Annotation.id.in_(
                select(AnnotationFacet.annotation_id).where(
                    AnnotationFacet.facet_type == "trigger", AnnotationFacet.value == trigger_value
                )
            )
        )
    annotations = list(session.scalars(statement.order_by(Annotation.updated_at.desc())))
    return [_annotation_read(annotation) for annotation in annotations]


@app.get("/api/exports/annotations")
def export_annotations(session: Session = Depends(get_session)) -> StreamingResponse:
    annotations = search_annotations(q=None, area=None, annotation_type=None, bail_proceeding=None, bail_result=None, bail_ground=[], bail_case_material=[], trigger=[], session=session)
    records = []
    for annotation in annotations:
        document = session.get(Document, annotation.document_id)
        paragraphs = list(
            session.scalars(
                select(Paragraph)
                .join(AnnotationParagraph, AnnotationParagraph.paragraph_id == Paragraph.id)
                .where(AnnotationParagraph.annotation_id == annotation.id)
                .order_by(Paragraph.ordinal)
            )
        )
        records.append(
            {
                "annotation": annotation.model_dump(mode="json"),
                "document": {
                    "id": document.id,
                    "title": document.title,
                    "neutral_citation": document.neutral_citation,
                    "court": document.court,
                    "decision_date": document.decision_date.isoformat() if document.decision_date else None,
                    "sha256": document.sha256,
                    "bail_proceeding": document.bail_proceeding,
                    "bail_result": document.bail_result,
                    "bail_grounds": document.bail_grounds or [],
                    "bail_case_material": document.bail_case_material or [],
                    "bail_case_note": document.bail_case_note,
                } if document else None,
                "paragraphs": [ParagraphRead.model_validate(paragraph).model_dump(mode="json") for paragraph in paragraphs],
            }
        )
    payload = json.dumps(
        {
            "format": "heimdall-annotation-export",
            "format_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "annotations": records,
        },
        indent=2,
    ).encode("utf-8")
    return StreamingResponse(iter([payload]), media_type="application/json", headers={"Content-Disposition": "attachment; filename=heimdall-annotations.json"})


def _backup_read(path: Path) -> BackupRead:
    return BackupRead(
        filename=path.name,
        bytes=path.stat().st_size,
        created_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
    )


@app.post("/api/backups", response_model=BackupRead, status_code=201)
def create_local_backup() -> BackupRead:
    return _backup_read(create_backup())


@app.get("/api/backups", response_model=list[BackupRead])
def list_local_backups() -> list[BackupRead]:
    return [_backup_read(path) for path in sorted(BACKUPS_DIR.glob("*.sqlite3"), reverse=True)]


@app.post("/api/statutes/criminal-code/import", response_model=StatuteSnapshotRead, status_code=201)
def import_latest_criminal_code(session: Session = Depends(get_session)) -> StatuteSnapshot:
    try:
        return import_criminal_code(session)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=502, detail=f"Could not import the official Criminal Code XML: {exc}") from exc


@app.post("/api/statutes/criminal-code/import-at", response_model=StatuteSnapshotRead, status_code=201)
def import_criminal_code_at_date(in_force_date: date, session: Session = Depends(get_session)) -> StatuteSnapshot:
    try:
        return import_criminal_code_at(session, in_force_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=502, detail=f"Could not import the official historical Criminal Code: {exc}") from exc


@app.get("/api/statutes", response_model=list[StatuteSnapshotRead])
def list_statutes(session: Session = Depends(get_session)) -> list[StatuteSnapshot]:
    return list(session.scalars(select(StatuteSnapshot).order_by(StatuteSnapshot.downloaded_at.desc())))


@app.get("/api/statutes/{snapshot_id}/provisions", response_model=list[StatuteProvisionRead])
def list_provisions(snapshot_id: str, q: str | None = Query(None), session: Session = Depends(get_session)) -> list[StatuteProvision]:
    snapshot = session.get(StatuteSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Statute snapshot not found")
    refresh_legacy_snapshot(session, snapshot)
    statement = select(StatuteProvision).where(StatuteProvision.snapshot_id == snapshot_id)
    citation_search = False
    if q:
        cleaned = q.strip().lower().removeprefix("section ").removeprefix("s.").strip()
        citation = f"s. {cleaned}"
        if re.fullmatch(r"\d[\da-z.()]*", cleaned):
            citation_search = True
            statement = statement.where(or_(StatuteProvision.citation.ilike(citation), StatuteProvision.citation.ilike(f"{citation}(%")))
        else:
            term = f"%{q.strip()}%"
            statement = statement.where(or_(StatuteProvision.text.ilike(term), StatuteProvision.heading.ilike(term), StatuteProvision.marginal_note.ilike(term), StatuteProvision.definition_term.ilike(term)))
    results = list(session.scalars(statement.order_by(StatuteProvision.ordinal).limit(500)))
    if not citation_search:
        return results
    all_nodes = list(session.scalars(select(StatuteProvision).where(StatuteProvision.snapshot_id == snapshot_id)))
    by_key = {node.node_key: node for node in all_nodes if node.node_key}
    included = {node.node_key: node for node in results if node.node_key}
    for node in list(included.values()):
        parent_key = node.parent_key
        while parent_key and parent_key not in included:
            parent = by_key.get(parent_key)
            if not parent:
                break
            included[parent_key] = parent
            parent_key = parent.parent_key
    return sorted(included.values(), key=lambda node: node.ordinal)


@app.get("/api/statutes/{snapshot_id}/sections", response_model=StatuteSectionPageRead)
def list_sections(
    snapshot_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    snapshot = session.get(StatuteSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Statute snapshot not found")
    refresh_legacy_snapshot(session, snapshot)
    statement = select(StatuteProvision).where(
        StatuteProvision.snapshot_id == snapshot_id,
        StatuteProvision.kind == "section",
        StatuteProvision.parent_key.is_(None),
    )
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(session.scalars(statement.order_by(StatuteProvision.ordinal).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@app.get("/api/statutes/{snapshot_id}/compare/{other_snapshot_id}", response_model=StatuteComparisonRead)
def compare_statute_versions(snapshot_id: str, other_snapshot_id: str, citation: str = Query(...), session: Session = Depends(get_session)) -> StatuteComparisonRead:
    earlier = session.get(StatuteSnapshot, snapshot_id)
    later = session.get(StatuteSnapshot, other_snapshot_id)
    if not earlier or not later:
        raise HTTPException(status_code=404, detail="Statute snapshot not found")
    refresh_legacy_snapshot(session, earlier)
    refresh_legacy_snapshot(session, later)
    try:
        return compare_snapshots(session, earlier, later, citation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/statutes/{snapshot_id}/provisions/{citation:path}", response_model=StatuteProvisionRead)
def get_provision(snapshot_id: str, citation: str, session: Session = Depends(get_session)) -> StatuteProvision:
    provision = session.scalar(select(StatuteProvision).where(StatuteProvision.snapshot_id == snapshot_id, StatuteProvision.citation == citation))
    if not provision:
        raise HTTPException(status_code=404, detail="Provision not found")
    return provision
