# Heimdall Near-Term Roadmap

**Status:** Active
**Last reviewed:** 2026-07-31

This file preserves the near-term implementation plan when chat context is unavailable. `VISION.md` remains the durable purpose, `ARCHITECTURE.md` remains the technical blueprint, and `ONTOLOGY.md` remains the controlled-vocabulary source of truth.

## Current Objective

Make the Phase 1 judgment-annotation workflow dependable enough for repeated use on real BC and SCC bail decisions. Let observed friction drive changes before introducing AI or a knowledge graph.

## Now — Calibrate Judgment Import

- Test extraction against real BCPC, BCSC, BCCA, and SCC judgment PDFs.
- Treat court-native downloads/web-print PDFs and CanLII PDFs as the first supported source families, with regression fixtures for each observed layout.
- Detect and exclude cover/title pages from the judgment page count.
- Remove repeating running headers, page numbers, and CanLII citation footers.
- Join numbered paragraphs that continue across physical page breaks.
- Preserve section headings without treating them as selectable legal propositions.
- Retain accurate judgment-page provenance for every extracted paragraph.
- Add a safe re-extraction workflow for documents that have no annotations.
- Flag image-only/scanned PDFs that require future OCR rather than silently producing poor text.
- After PDF ingestion is dependable, evaluate direct URL/HTML import from court sites and CanLII while retaining an immutable local source copy.

Completion criterion: the extracted-text pane faithfully represents the numbered judgment paragraphs in a representative bail-case test set.

## Next — Protect Canonical Knowledge

1. Introduce versioned database migrations before the schema accumulates real data.
2. Add immutable annotation revision history before substantial annotation work begins.
3. Add tested backup, export, and restore workflows for the database and original source files.
4. Permit manual correction of extraction while preserving the immutable original PDF and correction history.

Completion criterion: valuable annotations can be edited, migrated, backed up, and restored without losing provenance or history.

## Next — Improve Reading and Annotation Speed

- Replace the interim native-browser PDF frame with PDF.js when page synchronization work begins.
- Link an extracted paragraph to its corresponding rendered PDF page.
- Make selecting a paragraph focus the annotation panel without losing reading position.
- Expand keyboard-first navigation and multi-paragraph selection.
- Refine defaults based on observed bail annotation usage.

Completion criterion: a routine proposition can be captured accurately in a few seconds.

## Before Phase 3 — Normalize Relationships

- Replace JSON relationship placeholders with linked authority and relationship records.
- Give each directional relationship explicit source, target, type, commentary, provenance, and version.
- Migrate existing relationship data before it becomes substantial.

Completion criterion: cross-case relationships are queryable and ready for graph-aware retrieval without changing canonical annotation identity.

## Deliberately Deferred

- Autonomous legal analysis
- AI-authored canonical annotations
- Cloud dependencies for routine work
- Graph databases
- OCR until scanned judgments are actually encountered
- Elaborate visual polish unrelated to annotation speed

## Working Rule

Do not expand the system speculatively. Import and annotate a small set of real bail decisions, record recurring friction here, and promote only repeated problems into architecture or ontology changes.
