# Backend guide

**FastAPI (Python 3.11+) + PostgreSQL 14+.** The dashboard and `/api/v1` are served by the FastAPI backend (`backend-fastapi/`). The Node.js code is split in two:

- **`server/core.mjs`** (with `services.mjs`, `db/`, `config.mjs`) is the core with no web server. `scripts/train.mjs`, `fetch-psi.mjs` and `migrate.mjs` use it, and FastAPI's admin buttons run the first two.
- **`server/fastify/`** is a separate, optional Fastify web server with its own routes (`npm run start:fastify`, port 8080). It is not deployed. It exists for the Node API tests.

---

## 1. Server setup (PostgreSQL installed directly on the server)

These are the exact steps used to verify the deployment. Run them as a sudo user on Ubuntu or Debian.

```bash
# 0. Prerequisites: Python 3.11+, Node.js 22.13+ (training / PSI refresh), PostgreSQL 14+, poppler (PDF text)
sudo apt install -y python3-venv poppler-utils nginx
python3 --version && node -v && psql --version

# 1. Code + dependencies
sudo useradd --system --create-home --home-dir /opt/flame-in-freefall fif
sudo -u fif git clone <repo-url> /opt/flame-in-freefall
cd /opt/flame-in-freefall && sudo -u fif npm ci --omit=dev
sudo -u fif python3 -m venv backend-fastapi/.venv
sudo -u fif backend-fastapi/.venv/bin/pip install -r backend-fastapi/requirements.txt

# 1b. Main UI (React dashboard, served at "/")
cd frontend && sudo -u fif npm ci && sudo -u fif npm run build && cd ..

# 2. Database role + database (one time, as the postgres superuser)
sudo -u postgres psql -v app_password='a-long-random-password' -f server/db/setup/create_database.sql

# 3. Settings (read by FastAPI and by the Node scripts)
sudo -u fif cp backend-fastapi/.env.example backend-fastapi/.env && sudo chmod 600 backend-fastapi/.env
sudo -u fif nano backend-fastapi/.env      # DATABASE_URL, FIF_ADMIN_TOKEN (openssl rand -hex 32), FIF_DOCUMENTS_DIR

# 4. Run as a service. On first start it applies the migrations and seeds 24 investigations,
#    2,009 PSI test points and the 4 trained models, so there is no separate migrate step.
sudo cp deploy/flame-in-freefall.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now flame-in-freefall
curl -s http://127.0.0.1:8000/api/v1/livez       # {"status":"ok"}
curl -s http://127.0.0.1:8000/api/v1/health      # counts, migrations, models

# 5. nginx in front (TLS)
sudo cp deploy/nginx.conf /etc/nginx/sites-available/flame-in-freefall   # set server_name, then certbot for TLS
sudo ln -s /etc/nginx/sites-available/flame-in-freefall /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx

# 6. Optional: download and index the NASA PDF documents for cited answers (POST /ask)
cd backend-fastapi && sudo -u fif .venv/bin/python scripts/psi_download.py && cd ..

# 7. Users: one API key per person or application (run from /opt/flame-in-freefall)
npm run apikey -- create alice reader
npm run apikey -- create ops-team admin
npm run apikey -- list
npm run apikey -- revoke 3

# 8. Refresh from NASA PSI (also retrains the models)
curl -X POST -H "Authorization: Bearer $FIF_ADMIN_TOKEN" https://your.domain/api/v1/admin/ingest
```

The migration is **idempotent** and **records itself** in `schema_migrations`. You can run it by hand as above, or let the app apply it at startup, and it is never applied twice. Future schema changes arrive as `002_*.sql`, `003_*.sql` and so on, applied the same way.

---

## 2. Database schema (PostgreSQL)

Source: [`server/db/migrations/postgres/001_init.sql`](../server/db/migrations/postgres/001_init.sql)

```
psi_investigations 1──* psi_tables 1──* psi_test_points
models (id, version) 1──* predictions
api_keys · jobs · meta · http_cache · schema_migrations
```

| Table | Key columns | Purpose | Notable constraints / indexes |
|---|---|---|---|
| `psi_investigations` | `accession` PK, `doc jsonb`, generated `accession_num`, generated `search tsvector` | One row per NASA PSI investigation | `CHECK accession ~ '^PSI-\d+$'`; GIN on `doc` (jsonb_path_ops); GIN full-text on title, objectives, hypothesis and Earth benefits |
| `psi_tables` | `id` identity PK, `accession` FK, `columns jsonb`, `row_count` | Experimental test-matrix tables | `UNIQUE (accession, file)`; `ON DELETE CASCADE`; ids stable across re-ingests |
| `psi_test_points` | `(table_id, row_index)` PK, `cells jsonb` | One row per ISS test point (2,009) | `CHECK jsonb_typeof(cells) = 'array'` |
| `models` | `(id, version)` PK, `artifact jsonb`, `score`, `active` | Versioned ML models | Partial unique index: **exactly one active version per model** |
| `predictions` | identity PK, `(model_id, version)` FK, `input jsonb`, `output` | Prediction audit log | Index `(model_id, created_at DESC)`; purged after `FIF_PREDICTION_RETENTION_DAYS` |
| `api_keys` | identity PK, `name`, `role`, `key_hash` UNIQUE, `key_prefix` | Multi-user access | Only SHA-256 hashes stored; `CHECK role IN ('reader','admin')`; soft revoke |
| `jobs` | identity PK, `kind`, `status`, `detail jsonb` | Ingest and training history | Partial unique index: **at most one running job per kind**, across all servers |
| `meta` | `key` PK | Data and model generations, PSI provenance | Generation bumps send `NOTIFY fif_generation` |
| `http_cache` | `url` PK, `body`, `fetched_at` | Upstream NASA PSI response cache | Index on `fetched_at`; purged after `FIF_CACHE_RETENTION_DAYS` |
| `schema_migrations` | `version` PK | Applied migrations | Applied under an advisory lock |

Design choices:
- **Typed columns plus JSONB.** Fields used for querying and joins get typed columns. NASA's documents and model artifacts stay JSONB, so a NASA schema change never breaks ingestion.
- **The database enforces the rules that matter** (one active model, one running job, valid accessions and roles). This holds even with several servers and concurrent requests.
- **Bulk writes.** Each table's test points are inserted in one `INSERT … SELECT FROM jsonb_array_elements`.

---

## 3. Architecture and performance

| Layer | Choice | Why |
|---|---|---|
| Web server | **FastAPI** on uvicorn (Python 3.11+) | Async PostgreSQL pool (psycopg 3), Pydantic validation feeds the OpenAPI docs; serves the dashboard and `/api/v1` |
| Node core | Node.js 22 LTS, `server/core.mjs` (no web server) | Training and PSI ingest reuse the same ML code as the browser (`assets/js/training.js`) |
| Optional | Fastify 5 server in `server/fastify/` | A separate Node implementation of the API, kept for its tests; not deployed |
| API style | **REST + OpenAPI 3** | Read-heavy and cacheable (ETag, 304, CDN), callable from any tool, self-documenting |
| Database | **PostgreSQL 16** (`pg` pool) | Concurrent writes, constraints, JSONB + GIN, full-text search, LISTEN/NOTIFY, mature backups |
| Caching | In-process LRU (generation-keyed) + HTTP ETag/304 + DB upstream cache | Hot reads never touch the database; invalidation is instant via NOTIFY |
| Scaling | `uvicorn --workers N` in the service file, then more servers on the same database | Stateless workers; locks and constraints live in PostgreSQL |

**Measured** on 4 vCPU, 4 workers, PostgreSQL 16 on the same machine, 50 concurrent connections, with security headers, authentication, metrics and request ids enabled, and the load generator on the same cores:

| Endpoint | Requests/s | p50 | p99 | Errors |
|---|---|---|---|---|
| GET /investigations (ranked) | 22,190 | 1 ms | 10 ms | 0 |
| GET /investigations/{id} | 15,486 | 2 ms | 11 ms | 0 |
| GET /models | 11,957 | 3 ms | 11 ms | 0 |
| GET /psi/tables/{id} (500 rows) | 17,110 | 2 ms | 9 ms | 0 |
| GET /psi/search (full-text) | 42,645 | 0 ms | 5 ms | 0 |
| POST /models/{id}/predict | 26,789 | 1 ms | 8 ms | 0 |
| GET /livez (DB round-trip) | 24,133 | 1 ms | 6 ms | 0 |

Compression: `assets/data/models.js` goes from 400 KB to 70 KB with Brotli, and API JSON shrinks by about 70%.

---

## 4. Security

- **Authentication**: `Authorization: Bearer <key>` or `X-API-Key`. Roles are `reader` and `admin`. `FIF_REQUIRE_API_KEY=true` makes every read require a key; `/livez`, `/health` and the OpenAPI spec stay public. Revocation applies to every server immediately via NOTIFY.
- **Admin routes** (ingest, train, cache, API keys, retention, metrics) need the admin role. Without `FIF_ADMIN_TOKEN` (development only), they accept loopback requests only. Production refuses to start without the token.
- **Headers**: strict CSP (self plus Google Fonts), HSTS, `X-Content-Type-Options`, `frame-ancestors 'none'`, Referrer-Policy and others (via helmet).
- **Input validation** on every route (JSON schema). Body limit 512 KB. Rate limit per API key, or per IP when anonymous (`FIF_RATE_LIMIT_PER_MIN`); Claude is limited to 10 per minute.
- **Secrets** live only in `/etc/flame-in-freefall.env` (chmod 600). API keys are stored as SHA-256 hashes, admin tokens are compared in constant time, and no contact details are stored from PSI.
- The database role owns only its own schema and has no superuser rights.

---

## 5. Operations

| Task | How |
|---|---|
| Logs | `journalctl -u flame-in-freefall -f`: JSON lines with `reqId`, method, URL, status and latency |
| Health | `GET /api/v1/livez` (load balancer); `GET /api/v1/health` (full status, stats cached 5 s) |
| Metrics | `GET /api/v1/metrics` (admin, Prometheus format): request counts, latency histograms, cache hits, DB pool, memory |
| Backups | `pg_dump -Fc fif > fif-$(date +%F).dump`, daily via cron; restore with `pg_restore -d fif` |
| Refresh data | `POST /api/v1/admin/ingest` or `npm run fetch-psi` (behind a proxy: `NODE_USE_ENV_PROXY=1`) |
| Retrain | `POST /api/v1/admin/train` or `npm run train`; versions are kept in `models` |
| Retention | Automatic every hour; on demand with `POST /api/v1/admin/retention/run` |
| Upgrade | `git pull && npm ci --omit=dev && sudo systemctl restart flame-in-freefall` (pending migrations apply at start) |
| Tests | `npm test` (engine and ML; API tests when `TEST_DATABASE_URL` is set) and `npm run test:postgres` |

---

## 6. Recommendations as usage grows

1. **Now:** one server, `uvicorn --workers 4`, PostgreSQL on the same machine, nginx with TLS, and daily `pg_dump`. This handles thousands of requests per second.
2. **More traffic or high availability:** run two or more app servers behind nginx or a load balancer against one managed PostgreSQL. Caches stay consistent via NOTIFY, and jobs and models stay safe via constraints and advisory locks.
3. **Add Redis only then,** for a shared rate-limit store, since rate limits are currently per process. The response cache doesn't need it.
4. **Background job queue:** if ingests grow (more PSI research areas), move them to a worker process using `pg-boss`, which runs on the same PostgreSQL, so API servers never do long jobs.
5. **Observability:** scrape `/metrics` with Prometheus and Grafana, and ship the JSON logs to your log platform.
