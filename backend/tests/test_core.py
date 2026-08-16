from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, ensure_schema
from app.extraction import extract_paragraphs_from_pages
from app.main import app
from app.models import Document, Paragraph
from app.ontology import load_ontology
from app.ontology_registry import synchronize_ontology_registry
from app.statutes import parse_archived_provisions, parse_provisions


SAMPLE_CODE = b"""<?xml version='1.0'?>
<Statute><Body><Section><MarginalNote>Release</MarginalNote><Label>515</Label><Subsection><Label>(10)</Label><Paragraph><Label>(b)</Label><Text>Secondary ground.</Text></Paragraph></Subsection></Section></Body></Statute>"""

DEFINITION_CODE = b"""<?xml version='1.0'?>
<Statute><Body><Section><MarginalNote>Definitions</MarginalNote><Label>2</Label><Text>In this Act,</Text><Definition><Text><DefinedTermEn>Act</DefinedTermEn> includes</Text><Paragraph><Label>(a)</Label><Text>an Act of Parliament.</Text></Paragraph></Definition></Section></Body></Statute>"""

ARCHIVED_CODE = b"""<!doctype html><p class='MarginalNote'>Release</p><p class='Section'><strong><a class='sectionLabel'><span class='sectionLabel'>515</span></a></strong> A release order may be made.</p><p class='MarginalNote'>Grounds</p><p class='Subsection'><span class='lawlabel'>(10)</span> Detention is justified only if</p><p class='Paragraph'><span class='lawlabel'>(b)</span> public safety requires it.</p>"""

BODY_ONLY_CODE = b"""<?xml version='1.0'?>
<Statute><Body><Section><Label>1</Label><Text>Current text.</Text></Section></Body><RelatedOrNotInForce><Section><Label>999</Label><Text>Future text.</Text></Section></RelatedOrNotInForce></Statute>"""


def reset_database() -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS annotation_search")
        connection.exec_driver_sql("DROP TABLE IF EXISTS schema_migrations")
    ensure_schema()


def test_parser_preserves_nested_citations() -> None:
    provisions = parse_provisions(SAMPLE_CODE)
    assert [item["citation"] for item in provisions] == ["s. 515", "s. 515(10)", "s. 515(10)(b)"]


def test_parser_keeps_definition_content_out_of_section_body() -> None:
    provisions = parse_provisions(DEFINITION_CODE)

    section, definition, paragraph = provisions
    assert section["text"] == "In this Act,"
    assert definition["definition_term"] == "Act"
    assert definition["text"] == "Act includes"
    assert paragraph["citation"] == "s. 2(a)"
    assert paragraph["parent_key"] == definition["node_key"]


def test_archived_parser_preserves_historical_bail_hierarchy() -> None:
    provisions = parse_archived_provisions(ARCHIVED_CODE)

    assert [item["citation"] for item in provisions] == ["s. 515", "s. 515(10)", "s. 515(10)(b)"]
    assert provisions[-1]["text"] == "public safety requires it."


def test_parser_excludes_non_operative_material_outside_the_statute_body() -> None:
    provisions = parse_provisions(BODY_ONLY_CODE)

    assert [item["citation"] for item in provisions] == ["s. 1"]


def test_judgment_extraction_skips_cover_and_joins_page_breaks() -> None:
    pages = [
        "Citation: R. v. Test\nIN THE PROVINCIAL COURT\nORAL REASONS FOR JUDGMENT",
        "R. v. Test Page 1\n[1] First paragraph begins here and continues\n2026 BCPC 1 (CanLII)",
        "R. v. Test Page 2\non the following judgment page.\nOnus\n[2] Second paragraph.\n[DISCUSSION OMITTED]\n[3] Third paragraph.\n2026 BCPC 1 (CanLII)",
    ]
    paragraphs = extract_paragraphs_from_pages(pages)

    assert [item["label"] for item in paragraphs] == ["1", "heading", "2", "3"]
    assert paragraphs[0]["text"] == "First paragraph begins here and continues on the following judgment page."
    assert paragraphs[0]["source_page_start"] == 1
    assert paragraphs[0]["source_page_end"] == 2
    assert paragraphs[1]["text"] == "Onus"
    assert paragraphs[2]["text"] == "Second paragraph. [DISCUSSION OMITTED]"
    assert all("CanLII" not in str(item["text"]) and "Page 2" not in str(item["text"]) for item in paragraphs)


def test_bracketed_judgment_does_not_treat_numbered_quotes_as_paragraphs() -> None:
    pages = [
        "[1] First paragraph.\nTrial Proceedings\nJury selection\n[2] Second paragraph introduces a quotation:\n[268] Quoted transcript paragraph.\n[269] Another quoted paragraph.\nSo I think we will leave it at that …\n[3] Third paragraph."
    ]

    paragraphs = extract_paragraphs_from_pages(pages)

    assert [item["label"] for item in paragraphs] == ["1", "heading", "heading", "2", "3"]
    assert paragraphs[1]["text"] == "Trial Proceedings"
    assert paragraphs[2]["text"] == "Jury selection"
    assert paragraphs[3]["text"].endswith("[269] Another quoted paragraph. So I think we will leave it at that …")


def test_extraction_omits_publisher_matter_after_final_paragraph() -> None:
    pages = ["[1] Reasons.\n[2] The appeal is dismissed.\nAppeal dismissed.\nSolicitors for the appellant: Example LLP."]

    paragraphs = extract_paragraphs_from_pages(pages)

    assert [item["label"] for item in paragraphs] == ["1", "2"]
    assert paragraphs[-1]["text"] == "The appeal is dismissed."


def test_annotation_validation_and_statute_lookup(monkeypatch, tmp_path) -> None:
    reset_database()
    monkeypatch.setattr("app.statutes._download_xml", lambda: SAMPLE_CODE)
    monkeypatch.setattr("app.statutes._current_to_date", lambda: date(2026, 6, 14))
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        ontology = client.get("/api/ontology").json()
        assert ontology["version"] == "0.4.0"
        assert ontology["snapshot"]["annotation_fields"][0]["field"] == "Case"
        assert ontology["vocabularies"]["Research Track"] == ["Merits", "Sentencing", "Bail", "Charter and Procedure", "Other"]
        assert "Appeal granted" in ontology["vocabularies"]["Bail Result"]
        assert "Indigenous accused / Gladue" in ontology["vocabularies"]["Bail Factors"]
        registered_ontologies = client.get("/api/ontology/versions")
        assert registered_ontologies.status_code == 200
        assert registered_ontologies.json()[0]["version"] == "0.4.0"
        assert registered_ontologies.json()[0]["snapshot_json"]["vocabulary_definitions"]["Bail Factors"][0]["value"] == "Ground — Primary"
        assert client.get("/api/ontology/value-migrations").json() == []

        imported = client.post("/api/statutes/criminal-code/import")
        assert imported.status_code == 201, imported.text
        snapshot = imported.json()
        assert snapshot["current_to_date"] == "2026-06-14"
        sections = client.get(f"/api/statutes/{snapshot['id']}/sections", params={"limit": 1})
        assert sections.status_code == 200
        assert sections.json()["total"] == 1
        assert sections.json()["offset"] == 0
        assert sections.json()["items"][0]["citation"] == "s. 515"
        provisions = client.get(f"/api/statutes/{snapshot['id']}/provisions", params={"q": "515(10)(b)"})
        assert provisions.status_code == 200
        assert [item["citation"] for item in provisions.json()] == ["s. 515", "s. 515(10)", "s. 515(10)(b)"]

        from app.database import SessionLocal
        with SessionLocal() as session:
            document = Document(title="R. v. Test", source_filename="test.pdf", stored_path="documents/test/original.pdf", sha256="test", extraction_status="complete")
            session.add(document)
            session.flush()
            paragraph = Paragraph(document_id=document.id, ordinal=1, label="1", text="A test proposition.", source_page_start=1, source_page_end=1)
            session.add(paragraph)
            session.commit()
            document_id, paragraph_id = document.id, paragraph.id

        annotation = client.post("/api/annotations", json={
            "document_id": document_id,
            "paragraph_ids": [paragraph_id],
            "proposition": "The court states a bail principle.",
            "decision_track": "Bail",
            "bail_proceeding": "Initial release (ss. 515/516)",
            "bail_issue": "Detention ground",
            "bail_result": "Detained",
            "bail_factors": ["Ground — Tertiary", "Indigenous accused / Gladue"],
            "annotation_type": "Principle",
            "areas": ["Bail"],
            "authority_weight": "Routine",
            "function": "States Rule",
        })
        assert annotation.status_code == 201, annotation.text
        assert annotation.json()["ontology_version"] == "0.4.0"
        assert annotation.json()["bail_issue"] == "Detention ground"
        assert annotation.json()["bail_factors"] == ["Ground — Tertiary", "Indigenous accused / Gladue"]

        retrieved = client.get("/api/annotations", params=[
            ("bail_factor", "Ground — Tertiary"),
            ("bail_factor", "Indigenous accused / Gladue"),
            ("bail_result", "Detained"),
        ])
        assert retrieved.status_code == 200
        assert [item["id"] for item in retrieved.json()] == [annotation.json()["id"]]

        full_text = client.get("/api/annotations", params={"q": "test proposition"})
        assert full_text.status_code == 200
        assert [item["id"] for item in full_text.json()] == [annotation.json()["id"]]

        revisions = client.get(f"/api/annotations/{annotation.json()['id']}/revisions")
        assert revisions.status_code == 200
        assert revisions.json()[0]["revision_number"] == 1
        assert revisions.json()[0]["snapshot_json"]["paragraph_ids"] == [paragraph_id]

        update_payload = {**annotation.json(), "proposition": "The court states a revised bail principle.", "change_note": "Clarified wording."}
        update_payload.pop("id")
        update_payload.pop("ontology_version")
        update_payload.pop("created_at")
        update_payload.pop("updated_at")
        updated = client.patch(f"/api/annotations/{annotation.json()['id']}", json=update_payload)
        assert updated.status_code == 200, updated.text
        assert updated.json()["proposition"] == "The court states a revised bail principle."

        revisions = client.get(f"/api/annotations/{annotation.json()['id']}/revisions")
        assert [item["revision_number"] for item in revisions.json()] == [2, 1]
        assert revisions.json()[0]["change_note"] == "Clarified wording."

        exported = client.get("/api/exports/annotations")
        assert exported.status_code == 200
        export = exported.json()
        assert export["format"] == "heimdall-annotation-export"
        assert export["format_version"] == 1
        assert export["annotations"][0]["document"]["title"] == "R. v. Test"
        assert export["annotations"][0]["paragraphs"][0]["id"] == paragraph_id

        backup = client.post("/api/backups")
        assert backup.status_code == 201
        assert backup.json()["bytes"] > 0
        assert backup.json()["filename"].endswith(".sqlite3")

        incomplete_bail = client.post("/api/annotations", json={
            "document_id": document_id,
            "paragraph_ids": [paragraph_id],
            "proposition": "An incomplete bail classification.",
            "decision_track": "Bail",
            "annotation_type": "Principle",
            "areas": ["Bail"],
            "authority_weight": "Routine",
            "function": "States Rule",
        })
        assert incomplete_bail.status_code == 422


def test_registered_ontology_version_cannot_be_rewritten(monkeypatch, tmp_path) -> None:
    reset_database()
    original = (Path(__file__).parents[2] / "ONTOLOGY.md").read_text(encoding="utf-8")
    altered = tmp_path / "ONTOLOGY.md"
    altered.write_text(original.replace("| Bail | Judicial interim release, review, or bail pending appeal |", "| Bail | A deliberately rewritten meaning |", 1), encoding="utf-8")

    with SessionLocal() as session:
        synchronize_ontology_registry(session)

    monkeypatch.setattr("app.ontology.ONTOLOGY_PATH", altered)
    load_ontology.cache_clear()
    with SessionLocal() as session:
        with pytest.raises(RuntimeError, match="changed after version 0.4.0 was registered"):
            synchronize_ontology_registry(session)
        session.rollback()
    load_ontology.cache_clear()
