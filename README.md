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
