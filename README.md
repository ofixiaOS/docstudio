# Iplacex Studio

Iplacex Studio is a personal, local-first workspace for turning Iplacex rubrics into traceable academic projects. It separates the rubric, deliverables, study material, screenshots, document versions and AI conversation instead of treating the assignment as one large prompt.

## What works now

- Persistent projects in SQLite.
- Rubric extraction into individual criteria and deliverables.
- Section-by-section generation.
- Project sources indexed with FTS5 and optional Gemini embeddings.
- Short-term conversation context and long-term semantic memories.
- Rubric audit with a local fallback when the AI is unavailable.
- Autosave and manual document versions.
- Screenshot upload and insertion into the editor.
- Word export with headings, lists, code, emphasis, images and captions.
- Automatic discovery of supported files below the parent `iplacex` folder.

## Start

Double-click `iniciar_gamma.bat` or run:

```powershell
.\iniciar_gamma.ps1
```

The launcher creates an isolated Python virtual environment when needed, installs changed dependencies, starts both services and opens `http://127.0.0.1:5173`.

The backend uses port `8765` because port `8000` was occupied by a stale previous Uvicorn instance on the audited machine.

## Data and privacy

The database, uploads, evidence and exports stay under `backend/data`, which Git ignores. The Gemini key stays in `backend/.env`.

The application is local-first, not fully offline: when you analyze, generate, chat, audit with AI or create embeddings, the relevant text is sent to the configured Gemini API. Local persistence and FTS5 search continue to work without the API.

## Development

```powershell
cd backend
python -m pytest -q

cd ..\frontend
npm run lint
npm run build
```

See [AGENTS.md](AGENTS.md) for engineering invariants and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the audit and roadmap.
