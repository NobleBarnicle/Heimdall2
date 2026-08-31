# Heimdall Technical Architecture

**Status:** Initial blueprint
**Scope:** Phase 1 is authoritative; later phases are design constraints, not implementation commitments.

## 1. System Boundaries

Heimdall is a single-user, local-first desktop-oriented web application. A local FastAPI service owns the database and document files; a React client provides the annotation workflow.

```text
Browser UI (React + TypeScript + PDF.js)
              │ HTTP / JSON
              ▼
       Local API (FastAPI)
              │
              ├── SQLite database
              └── local document storage

Future only: local Ollama adapter → derived, reviewable AI outputs
```

The browser never accesses the database or document store directly. The AI adapter never has write access to canonical annotation records.

## 2. Phase 1 Responsibilities

| Component | Responsibility | Does not do |
| --- | --- | --- |
| Import service | Validate and store a PDF; create a document record | Infer legal significance |
| Text extraction service | Extract, retain, and index paragraph text with extraction metadata | Treat imperfect extraction as authoritative |
| Document reader | Present original PDF and extracted text side by side | Modify source material |
| Annotation service | Validate and persist human-entered propositions | Let an AI author annotations |
| Search service | Find documents and annotations using structured filters and text search | Produce legal conclusions |
| Export service | Create portable, provenance-preserving exports | Export AI output as canonical knowledge |
| Ontology loader | Read the approved controlled vocabulary | Embed duplicate vocabulary constants in code |

## 3. Canonical Data and Derived Data

Canonical data is created or approved by the user and is retained in the local database. It includes documents, source paragraphs, annotations, annotation revisions, statute snapshots and provisions, and the ontology version used for each annotation.

Derived data may be recreated and must remain separate: full-text indexes, extracted-text revisions, embeddings, local AI drafts, similarity suggestions, and case-card drafts. Every derived item records its source object IDs, generation date, model/provider details, and prompt version where applicable.

## 4. Initial Domain Model

All records use stable UUID primary keys, UTC creation and update timestamps, and soft deletion where appropriate. Canonical objects have immutable revision history.

### Document

- `id`, `title`, `neutral_citation`, `court`, `decision_date`, `bail_proceeding`, `bail_result`
- `source_filename`, `stored_path`, `sha256`
- `imported_at`, `extraction_status`, `extraction_version`

### Paragraph

- `id`, `document_id`, `ordinal`, `label`, `text`
- `source_page_start`, `source_page_end`, `extraction_confidence`

Paragraph labels retain the source judgment's numbering when available. Ordinal preserves display and navigation order. Extraction may be corrected manually without changing the original PDF.

### Statute snapshot and provision

- `statute_snapshot`: `id`, `short_title`, `citation`, `jurisdiction`, `source_url`, `source_format`, `source_sha256`, `current_to_date`, `downloaded_at`, `parser_version`
- `statute_provision`: `id`, `snapshot_id`, `section`, `subsection`, `paragraph`, `subparagraph`, `display_citation`, `heading`, `marginal_note`, `text`, `parent_id`, `ordinal`

The initial statute is the Canadian *Criminal Code*, R.S.C. 1985, c. C-46. Import the official Justice Laws XML as an immutable local source snapshot and parse every structural provision into navigable records. A future refresh creates a new snapshot; it never overwrites an existing one. Citations must be stable and linkable, for example `s. 515(10)(b)`.

### Annotation

- `id`, `document_id`, `proposition`
- `type`, `area`, `authority_weight`, `function`
- `relationship`, `boundary`, `trigger`, `commentary`
- `ontology_version`, `created_at`, `updated_at`, `deleted_at`

An annotation is linked to one or more paragraphs through `annotation_paragraph`. For Bail, the case-level proceeding and result are copied onto each annotation and synchronized when the user edits the case profile, preserving both portable exports and annotation revision history. Grounds in issue and case-specific material remain on the case itself, are mirrored into normalized `document_facet` records for indexed structured search, and are never repeated on individual propositions. Passage-level annotations retain one precise Bail Issue; saving a primary, secondary, or tertiary-ground proposition automatically adds that ground to the case profile. Other multi-value annotation classifications (`areas` and `triggers`) are mirrored into `annotation_facet` records. It may link related authorities through `annotation_related_authority`. The exact controlled values and validation rules come only from `ONTOLOGY.md`.

### Annotation revision

- `id`, `annotation_id`, `revision_number`, `snapshot_json`
- `changed_at`, `change_note`

Save a revision at creation and before each user-visible canonical change, including soft deletion. Never rewrite revision history.

## 5. Storage

Store SQLite data and imported PDFs in an application-data directory outside the source repository. The database stores relative document locations and SHA-256 hashes; it must not rely on absolute paths that make backups or migration brittle.

Recommended layout:

```text
application-data/
├── heimdall.sqlite3
├── documents/<document-id>/original.pdf
├── statutes/<statute-snapshot-id>/source.xml
├── exports/
└── backups/
```

Database migrations are recorded, versioned, and forward-only. A consistent SQLite backup is taken before migrations on an existing database; users can also make an on-demand backup from the app. Full-text indexes are derived, rebuildable SQLite FTS5 data and never replace canonical annotation records.

## 6. API Shape (Phase 1)

- `POST /documents` — import a PDF and metadata
- `GET /documents` and `GET /documents/{id}` — list or read documents
- `PATCH /documents/{id}/case-context` — save or correct shared Bail case context
- `GET /documents/{id}/file` — stream the stored PDF
- `GET /documents/{id}/paragraphs` — read extracted text
- `POST /documents/{id}/paragraphs/reextract` — explicitly run extraction again
- `GET /statutes` and `GET /statutes/{snapshot_id}` — list or read local statute snapshots
- `GET /statutes/{snapshot_id}/provisions` — search and retrieve parsed sections and subsections
- `GET /statutes/{snapshot_id}/provisions/{citation}` — retrieve a provision by canonical citation
- `GET /annotations` — search annotations with structured filters
- `POST /annotations` — create a human annotation
- `GET /annotations/{id}` — read an annotation and provenance
- `PATCH /annotations/{id}` — update and create a revision
- `DELETE /annotations/{id}` — soft-delete an annotation
- `GET /annotations/{id}/revisions` — read immutable annotation history
- `GET /exports/annotations` — export selected canonical annotations
- `GET /backups`, `POST /backups` — inspect or create local SQLite backups
- `GET /ontology` — expose the parsed, versioned controlled vocabulary

The API returns predictable error objects and validates every controlled field against the current ontology. It records the ontology version at annotation creation and update.

## 7. Annotation Workflow

1. Import a judgment and confirm its basic metadata.
2. Review the original PDF alongside extracted paragraphs.
3. Select one or more exact paragraphs.
4. For a Bail case, save the proceeding and result once, then create propositions using fast keyboard-first controls and ontology defaults.
5. Save the human-authored annotation and its provenance.
6. Search, filter, and export the curated corpus.

The Criminal Code can be searched and retrieved independently of judgment annotations. Its official source date is visible in the interface so users can distinguish the local snapshot from the law as it may currently stand.

The UI should make a common annotation take seconds. Initial focus is a bail-law workflow, but neither database fields nor API routes are bail-specific.

## 8. Ontology Governance

`ONTOLOGY.md` is the source of truth for all dropdown options and controlled-value validation. A small parser or build step may make it machine-readable, but must not create a second manually maintained vocabulary.

Changes to the ontology require:

1. an explicit version increment;
2. a migration strategy for existing values, if needed;
3. retaining the version on each annotation; and
4. recording why a new value was introduced, particularly after repeated `Other` use.

At first use of a version, Heimdall stores an immutable `ontology_version` snapshot containing the annotation-field rules, controlled values, and their meanings, with a semantic fingerprint. Startup rejects a source ontology whose fingerprint no longer matches an already registered version. `ontology_value_migration` records rename and retirement mappings from `ONTOLOGY.md`; it is explanatory and retrieval-oriented, not an automatic mutation of historic annotations. Adding a field requires a forward-only database migration plus API/UI support and an explicit decision on whether to backfill older records.

## 9. Future AI Boundary

An AI provider interface is introduced only in Phase 2. It accepts curated source material and produces a separately stored `DerivedArtifact` with provenance, model identity, prompt version, and human review state. It cannot call annotation-creation or update services.

The first provider is Ollama through an OpenAI-compatible interface. Other providers must be interchangeable without changing domain logic.

## 10. Quality and Safety Constraints

- No cloud service is required to import, annotate, search, or export.
- PDF source files are immutable after import; corrections are separate records.
- Every displayed proposition can link back to its document and exact paragraph(s).
- Search results distinguish canonical annotations from derived material.
- Human annotations are never silently changed by software or AI.
- Tests cover ontology validation, provenance links, revisions, and import/export round trips.
