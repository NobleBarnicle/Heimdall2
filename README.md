# Heimdall

Local-first legal knowledge engine for Canadian criminal law.

For day-to-day setup, commands, and troubleshooting, see [CHEATSHEET.md](CHEATSHEET.md).

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm install

.venv/bin/uvicorn app.main:app --app-dir backend --reload
npm run dev
```

Open the address printed by Vite (normally `http://localhost:5173`). The frontend proxies `/api` to the local FastAPI service.

By default, all imported source documents, statute XML snapshots, and the SQLite database live in `~/Library/Application Support/Heimdall`, outside the repository. A judgment PDF can begin anywhere convenient, such as Downloads; the import form copies it into Heimdall's managed local storage.

For disposable development data, set `HEIMDALL_DATA_DIR` before starting the API. Do not place irreplaceable legal data in the repository.

## Current scope

Phase 1 supports local PDF import, paragraph extraction and navigation, structured human annotations, annotation search/export, and importing the official English Criminal Code XML as a local, citation-addressable snapshot. AI integration is deliberately not included.

## Annotation data foundation

Annotations are canonical, human-authored records. Each save creates an immutable revision that preserves the selected paragraph IDs, controlled values, commentary, and ontology version at that time. Deleting an annotation is a soft deletion with its own final revision.

Search covers annotation propositions, commentary, and the exact source paragraphs. Structured multi-value classifications (areas, triggers, and bail factors) are also stored as normalized, indexed facets so they remain fast and filterable as the corpus grows.

The API applies recorded, forward-only local database migrations. Before it applies a migration to an existing database, it creates a consistent SQLite backup in:

```text
~/Library/Application Support/Heimdall/backups/
```

Use the **Back up** button beside Saved propositions before a substantial annotation session; the **Export** link downloads a versioned JSON file containing annotations, document identity, and the cited paragraph text. Neither backups nor exports are added to Git.

For the first pilot, ingest a deliberately varied set of 12–20 decisions and create 40–80 annotations. Note repeated use of an `Other` value or fields you consistently leave blank—those are the evidence for the next ontology and workflow changes.
