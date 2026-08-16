# Heimdall: Legal Knowledge Engine

## Vision

Build a local-first, AI-assisted legal knowledge platform for Canadian criminal law.

The core objective is not to replace legal analysis. The core objective is to capture the user's expert legal analysis in a structured, machine-readable form that compounds in value over time.

The system should allow the user to efficiently annotate judgments using a controlled ontology. Those annotations become the canonical source of truth. AI models consume and synthesize this curated knowledge rather than attempting to infer importance directly from raw judgments.

The architecture can assume that local LLMs will steadily improve over the coming years, but core workflows must work with Qwen3 14B (the current local model). Every major design decision should therefore maximize future compatibility and minimize coupling to any specific model or framework.

## Core Philosophy

- The human performs legal reasoning.
- The software performs organization.
- The AI performs synthesis.
- Legal judgment remains human-owned.

## Long-Term Vision

Create a private legal knowledge base that eventually contains:

- Criminal Code
- Charter
- BC and SCC criminal jurisprudence
- Sentencing authorities
- Personal legal commentary
- Cross-case relationships
- AI-generated synthesis built exclusively upon curated material

Over time the system should become an externalized extension of the user's legal reasoning rather than merely a searchable database.

Begin with one area of criminal law, such as bail. Perfect its workflow, then expand deliberately.

## Guiding Principles

- **Local-first:** Routine workflows keep all legal data on the user's hardware. Cloud APIs are optional enhancements, never dependencies.
- **AI is swappable:** No business logic may depend on a specific LLM.
- **Human analysis is canonical:** AI suggestions never overwrite human annotations. Human annotations are the authoritative record.
- **Structured over freeform:** Every annotation uses structured metadata whenever possible. Free-text commentary supplements structure rather than replacing it.
- **Speed matters:** Most annotations should take seconds. Prefer dropdowns, defaults, and keyboard shortcuts over typing.
- **Everything is versioned:** Ontology, schemas, prompts, knowledge objects, and database all evolve independently.

## High-Level Architecture

```text
PDF
  ↓
Document Import
  ↓
Paragraph Extraction
  ↓
Annotation Interface
  ↓
Structured Knowledge Database
  ↓
Search / Retrieval
  ↓
AI Synthesis
  ↓
User
```

The AI never writes directly into the database. It only produces derived work.

## Phased Delivery

### Phase 1 — Annotation Platform

Create the annotation platform without sophisticated AI.

Obtain the latest version of the Canadian Criminal Code and parse it so every section and subsection is easily referenced and retrieved going forward.

Features:

- Import PDF
- Display PDF
- Display extracted text
- Paragraph navigation
- Annotation panel
- Structured annotation storage
- Search annotations
- Export annotations

Completion criterion: a lawyer can quickly annotate a judgment and capture what is noteworthy or important in a structured form.

### Phase 2 — Local AI

Use local models only, initially Qwen3 14B via Ollama, to:

- Summarize annotations
- Draft case cards
- Answer questions from the curated corpus
- Identify related annotations

There is no autonomous legal analysis. All output is shown for approval and editing before any human decides to incorporate it.

### Phase 3 — Knowledge Graph

Introduce relationship-aware knowledge. For example, *Jordan* affirmed *Cody*, or *Grant* distinguished *Le*. Queries become relationship-aware.

### Phase 4 — Optional Cloud Enhancement

Use frontier models only as an optional enhancement for difficult synthesis, foundational SCC judgments, ontology refinement, and long-context analysis. Cloud access is never required for daily use.

## Annotation Philosophy

The unit of knowledge is not the case; it is the legal proposition.

Every proposition has provenance and is tied to exact paragraph(s) in a saved, linkable authority.

Each annotation includes:

- **Mandatory:** case, paragraph(s), type, area, authority weight, and function.
- **Optional:** relationship, boundary, trigger, commentary, and related authorities.

The ontology remains intentionally small and evolves through observed usage rather than speculative completeness. Monitor use of `Other`; repeated use should trigger an ontology revision.

## AI Responsibilities

Current local models may reliably perform:

- Semantic search
- Summarization
- Drafting
- Relationship suggestions
- Duplicate detection
- Finding similar propositions

Current local models must not autonomously:

- Determine ratio
- Determine authoritative passages
- Decide importance
- Rewrite human annotations

## Technical Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Frontend:** React, TypeScript, PDF.js
- **Database:** SQLite initially
- **AI:** Ollama through an OpenAI-compatible API layer; Open WebUI for experimentation
- **Version control:** Git

## Coding Philosophy

- Prefer readable code over clever code.
- Prefer mature libraries over custom implementations.
- Avoid unnecessary abstraction.
- Give every module one responsibility.
- Write every function so future LLMs can understand it.
- This is a personal tool, not a commercial product; visual polish is secondary to a dependable workflow.

## Project Success

The project succeeds if, after several years of use:

- the ontology has matured naturally;
- thousands of curated legal propositions exist;
- stronger future LLMs can immediately leverage the corpus without redesign; and
- the user's accumulated legal judgment has become an enduring, searchable knowledge asset.
