# Flame in Freefall: FastAPI backend

This is the Python backend for the NASA Space Apps 2026 challenge **Flame in Freefall**. It follows the
Challenge 6 ("FlameAtlas") plan of the team's backend developer guide. It ingests NASA PSI documents,
stores extracted test rows, ranks investigations by a rubric and serves cited answers. It uses the
same PostgreSQL database as the Node backend in `../server`; both can run at the same time.

## What it does with NASA data

These figures were measured on this backend with the real data:

| Data | Count |
|---|---|
| NASA PSI combustion investigations (official records) | 24 |
| PSI test points ingested from 22 published test matrices | 2,009 |
| Normalized test rows (fuel, O₂, pressure, flow, diluents, outcome, results) | 1,986 |
| NASA PDF documents downloaded and parsed (Reports, Science Documents) | 39 PDFs, 1,727 pages |
| Page-cited passages searchable by `POST /ask` | 4,453 (4,267 from PDFs, 186 from PSI records) |
| Pre-generated summaries and habitat briefs in the database | 30 |

Two PSI reports (BASS and SPICE final reports listed under PSI-26) return 404 from NASA's own storage.
The download job records this error and skips them.

## Endpoints

These follow the guide, under `/api/v1`. Interactive docs are at `/docs`.

| Guide | Endpoint | What it returns |
|---|---|---|
| `/habitats` | `GET /habitats`, `GET /habitats/{id}` | Spacecraft, station, Moon base, rover, Mars base and spacesuit, with design atmospheres, evidence coverage and ranked investigations |
| `/investigations` | `GET /investigations`, `GET /investigations/{PSI-n}` | PSI records, stored summary, measured test envelope, documents, and rank in each habitat |
| `POST /rank` | `POST /rank` | Rubric ranking, with every component and a reason; weights and filters can be changed |
| `/tests?fuel=&o2=` | `GET /tests`, `GET /tests/facets`, `GET /tests.csv` | Normalized ISS test rows, filtered by fuel (`ethylene` also matches `C2H4`), O₂, pressure, flow, diluent and outcome; the CSV export is streamed |
| `POST /ask` | `POST /ask` | Answer built only from NASA passages; each sentence cites a document and page |
| `/brief/{habitat}` | `GET /brief/{habitat}?format=json\|md\|html` | Printable or copyable fire-safety brief |
| Cached summaries | `GET /summaries/{PSI-n}` | Pre-generated summaries stored in PostgreSQL |
| | `GET /documents`, `GET /documents/{PSI-n}/{file}/pages/{page}` | Parsed documents, and the text of a cited page, so anyone can check a citation |
| | `GET /health`, `GET /livez` | Status, counts, migrations, pool, cache and AI configuration |
| | `POST /admin/...` | Document ingestion, re-indexing, summary regeneration, cache clearing and jobs (admin token) |

## How the AI works

- **Test-row extraction** (`app/extract/test_rows.py`):
  - Detects column roles in each NASA table and normalizes units per cell: mole fraction or %, and mmHg, bar, atm or kPa.
  - Ignores "final" and "after" values, which describe the result rather than the starting conditions.
  - Every row keeps its source table and row number.
- **PDF parsing** (`app/extract/pdf.py`):
  - Uses Poppler `pdftotext`, the engine behind several Python PDF libraries.
  - Pages are cleaned, wrapped lines are joined, and pages are split into passages of about 1,100 characters.
  - A passage never crosses a page, so every citation has an exact page number.
- **Retrieval** (`app/rag/retriever.py`): hybrid search, combining
  - BM25 with fire-safety synonyms;
  - PostgreSQL full-text search (`tsvector`);
  - reciprocal-rank fusion of the two lists.

  Reference lists are down-weighted, and an optional boost favours investigations relevant to a habitat.
- **Answers** (`app/rag/answer.py`):
  - **Offline (always available):** quotes NASA sentences that match the question, skipping bibliography entries and captions, and cites each one.
  - **With `ANTHROPIC_API_KEY`:** Claude answers from the same passages. The passages are sent as `search_result` blocks with citations turned on, so the API itself links each claim to a passage.
  - **Number guard (both modes):** every number in an answer must appear in a cited passage. If it doesn't, the answer lists it under `unverifiedNumbers` and is marked not grounded.
- **Ranking rubric** (`app/ranking.py`): atmosphere match measured from test rows, gravity, ventilation, fire scale, topical relevance (BM25) and data richness. The weights are documented in the code, and every score comes with its reasons.

## Run it

You need Python 3.11 or newer, PostgreSQL 14 or newer, and `poppler-utils` (`sudo apt install poppler-utils`).

```bash
cd backend-fastapi
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL (and FIF_ADMIN_TOKEN on a server)
.venv/bin/python run.py                 # dashboard at http://localhost:8000/ (Windows: .venv/Scripts/python.exe run.py)
```

On first start the app:
1. applies the database migrations (`../server/db/migrations/postgres/001_init.sql`, then `migrations/101_flameatlas.sql`);
2. seeds the 24 PSI investigations from `../assets/data/psi-snapshot.js` if the database is empty;
3. builds the test rows, metadata passages, summaries and briefs.

To apply the migrations by hand instead:

```bash
psql "$DATABASE_URL" -1 -v ON_ERROR_STOP=1 -f ../server/db/migrations/postgres/001_init.sql
psql "$DATABASE_URL" -1 -v ON_ERROR_STOP=1 -f migrations/101_flameatlas.sql
```

Download and index the NASA documents (about 73 MB for Reports and Science Documents). Re-running is safe, because files already downloaded are skipped:

```bash
.venv/bin/python scripts/psi_download.py
.venv/bin/python scripts/psi_download.py --categories "Engineering Documents" Presentations --max-mb 25   # more documents
.venv/bin/python scripts/precompute.py            # rebuild stored summaries and briefs
.venv/bin/python scripts/precompute.py --claude   # also grounded Claude summaries (needs ANTHROPIC_API_KEY)
```

On a server, use 4 workers behind nginx: see `../deploy/flame-in-freefall.service`, `../deploy/nginx.conf` and the steps in `../docs/BACKEND.md`.

## Tests

```bash
TEST_DATABASE_URL=postgres://fif:PASSWORD@localhost:5432/fif .venv/bin/python -m pytest -q   # 23 tests
..\start.cmd -Test                    # Windows: does the above with backend-fastapi/.env, then npm test
```

The tests run against a real PostgreSQL database seeded with real PSI data. They cover:
- unit parsing (messy cells, units, final values, PDF cleaning);
- extraction of a FLEX row;
- the number guard;
- every endpoint, including ETag/304, errors and admin authentication;
- the frozen API schema: `openapi.json` must match the code. After an intended API change, run `scripts/export_openapi.py`.

Measured on this container, single worker, cached responses:
- `/habitats`: 1.3 ms median;
- `/tests`: 4 ms;
- `/brief`: 2 ms;
- an uncached `/ask` over 4,453 passages: 53 ms.

## Choices compared with the guide

| Guide | Here | Why |
|---|---|---|
| boto3 (AWS Open Data) | PSI's presigned S3 URLs, streamed with httpx | The same S3 objects, with no AWS credentials needed. Resumable downloads with SHA-256 checks. |
| PyMuPDF / pdfplumber | Poppler `pdftotext` | Robust page-by-page text with no Python native build; pdfplumber can be added for table extraction. |
| SQLite / DuckDB | PostgreSQL | Several users and servers at once, full-text search, and shared with the Node training and ingest scripts. 1,986 rows doesn't need DuckDB. |
| Ollama + ChromaDB | Hybrid BM25 + PostgreSQL full-text; Claude optional | Works offline without a GPU or model download. Citations are exact pages, and numbers are checked. |
| Docker Compose | systemd unit | You asked for a direct install on the server, without Docker. |

## Licence

MIT (see `LICENSE`). NASA PSI data is CC0-1.0.
