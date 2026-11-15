-- =====================================================================
-- Flame in Freefall, FastAPI backend: PostgreSQL migration 105 (React dashboard data contract)
--
-- Tables behind the routes in frontend/DATA_CONTRACT.md (served under /api/..., see app/routers/frontend.py):
--   catalog_investigations   the curated investigation catalog in the dashboard's shape
--                            (seeded at startup from app/data/catalog.json, made by `npm run export-catalog`)
--   conversations            a signed-in user's chat threads with the RAG assistant
--   messages                 the questions and answers of each thread, with citations
-- Idempotent.
-- =====================================================================

CREATE TABLE IF NOT EXISTS catalog_investigations (
  id             text        PRIMARY KEY CHECK (id ~ '^[a-z0-9][a-z0-9-]{0,63}$'),
  psi_accession  text        CHECK (psi_accession IS NULL OR psi_accession ~ '^PSI-[0-9]{1,5}$'),
  doc            jsonb       NOT NULL,
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS catalog_investigations_psi_idx ON catalog_investigations (psi_accession);

CREATE TABLE IF NOT EXISTS conversations (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  title       text        NOT NULL DEFAULT '' CHECK (length(title) <= 200),
  habitat     text        CHECK (habitat IS NULL OR length(habitat) <= 100),
  role        text        NOT NULL CHECK (role IN ('researcher', 'engineer', 'student')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS conversations_user_idx ON conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  conversation_id  uuid        NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
  role             text        NOT NULL CHECK (role IN ('user', 'assistant')),
  text             text        NOT NULL CHECK (length(text) <= 20000),
  citations        jsonb       NOT NULL DEFAULT '[]'::jsonb,
  followups        jsonb       NOT NULL DEFAULT '[]'::jsonb,
  confidence       text        CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low', 'none')),
  source           text        NOT NULL DEFAULT '',
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages (conversation_id, id);
