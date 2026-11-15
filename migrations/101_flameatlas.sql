-- =====================================================================
-- Flame in Freefall, FastAPI backend: PostgreSQL migration 101 (FlameAtlas tables)
--
-- Requires the base schema first: ../server/db/migrations/postgres/001_init.sql
-- (PSI investigations, tables, test points, jobs, api_keys...). The FastAPI app applies both
-- automatically at startup; to run them by hand on the server, in order:
--   psql "$DATABASE_URL" -1 -v ON_ERROR_STOP=1 -f server/db/migrations/postgres/001_init.sql
--   psql "$DATABASE_URL" -1 -v ON_ERROR_STOP=1 -f backend-fastapi/migrations/101_flameatlas.sql
--
-- Versions 100+ belong to the FastAPI backend, so they never collide with the Node migrations.
-- Every statement is idempotent; the script records itself in schema_migrations.
--
--   test_rows    normalized test rows from PSI test matrices (fuel, O2, pressure, flow, outcome)
--   documents    NASA PSI documents (PDF reports, PSI metadata records)
--   doc_chunks   page-level passages, the unit of retrieval and citation for POST /ask
--   summaries    pre-generated summaries and habitat briefs (offline demo)
-- =====================================================================

CREATE TABLE IF NOT EXISTS test_rows (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  accession    text    NOT NULL,
  -- No foreign key: the Node backend TRUNCATEs psi_tables on re-ingest; the FastAPI app rebuilds
  -- test_rows whenever meta.data_generation changes (see app/store.py).
  table_id     integer NOT NULL,
  table_label  text    NOT NULL DEFAULT '',
  row_index    integer NOT NULL CHECK (row_index >= 0),
  fuel         text    NOT NULL DEFAULT '',
  o2_pct       real    CHECK (o2_pct IS NULL OR (o2_pct > 0 AND o2_pct <= 100)),   -- vol %
  pressure_kpa real    CHECK (pressure_kpa IS NULL OR pressure_kpa > 0),             -- kPa
  flow_cm_s    real    CHECK (flow_cm_s IS NULL OR flow_cm_s >= 0),                  -- cm/s
  gravity_g    real    NOT NULL DEFAULT 0,                                            -- 0 = microgravity
  diluents     jsonb   NOT NULL DEFAULT '{}'::jsonb,   -- {"CO2": 15.0, "He": 0} in vol %
  conditions   jsonb   NOT NULL DEFAULT '{}'::jsonb,   -- {"Flow Direction": "Concurrent"}
  outcome      text    NOT NULL DEFAULT '',            -- "Hot ignition: Yes; Self-ext or flow term: SE"
  measures     jsonb   NOT NULL DEFAULT '{}'::jsonb,   -- {"Burning rate; mm": 0.52}
  UNIQUE (table_id, row_index)
);
CREATE INDEX IF NOT EXISTS test_rows_accession_idx ON test_rows (accession);
CREATE INDEX IF NOT EXISTS test_rows_fuel_idx      ON test_rows (lower(fuel) text_pattern_ops);
CREATE INDEX IF NOT EXISTS test_rows_o2_idx        ON test_rows (o2_pct) WHERE o2_pct IS NOT NULL;
CREATE INDEX IF NOT EXISTS test_rows_pressure_idx  ON test_rows (pressure_kpa) WHERE pressure_kpa IS NOT NULL;

-- Not linked to psi_investigations by foreign key: documents survive a PSI re-ingest.
CREATE TABLE IF NOT EXISTS documents (
  id          text PRIMARY KEY,                 -- "PSI-159/PSI-159_Reports_FinalRpt_ACME.CFI-G.pdf" or "PSI-159/metadata"
  accession   text        NOT NULL CHECK (accession ~ '^PSI-[0-9]{1,5}$'),
  title       text        NOT NULL,
  kind        text        NOT NULL CHECK (kind IN ('pdf', 'metadata')),
  category    text        NOT NULL DEFAULT '',  -- PSI folder: "Reports", "Science Documents"...
  file_name   text        NOT NULL DEFAULT '',
  pages       integer     NOT NULL DEFAULT 0 CHECK (pages >= 0),
  bytes       bigint      NOT NULL DEFAULT 0 CHECK (bytes >= 0),
  sha256      text        NOT NULL DEFAULT '',
  source_url  text        NOT NULL DEFAULT '',
  parsed_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_accession_idx ON documents (accession);

CREATE TABLE IF NOT EXISTS doc_chunks (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id text    NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
  page        integer NOT NULL CHECK (page >= 1),
  chunk_index integer NOT NULL CHECK (chunk_index >= 0),
  section     text    NOT NULL DEFAULT '',      -- e.g. "Objectives" for metadata records
  text        text    NOT NULL,
  search      tsvector GENERATED ALWAYS AS (to_tsvector('english', section || ' ' || text)) STORED,
  UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS doc_chunks_search_idx   ON doc_chunks USING gin (search);
CREATE INDEX IF NOT EXISTS doc_chunks_document_idx ON doc_chunks (document_id, page);

CREATE TABLE IF NOT EXISTS summaries (
  kind            text        NOT NULL CHECK (kind IN ('investigation', 'brief')),
  subject         text        NOT NULL,       -- PSI accession or habitat id
  generator       text        NOT NULL,       -- "extractive-v1" or "claude:<model>"
  content         jsonb       NOT NULL,
  data_generation text        NOT NULL DEFAULT '',
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (kind, subject, generator)
);

-- New job kinds for document ingestion and summary generation.
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_kind_check;
ALTER TABLE jobs ADD CONSTRAINT jobs_kind_check CHECK (kind IN ('ingest', 'train', 'documents', 'summaries', 'test_rows'));

INSERT INTO schema_migrations (version, name) VALUES (101, '101_flameatlas.sql') ON CONFLICT (version) DO NOTHING;
