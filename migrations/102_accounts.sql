-- =====================================================================
-- Flame in Freefall, FastAPI backend: PostgreSQL migration 102 (user accounts)
--
--   users         people who sign up on the dashboard (email + scrypt password hash)
--   user_tokens   email-verification links and sign-in sessions; only SHA-256 hashes are stored
--
-- Applied automatically at startup (see app/db.py). Idempotent.
-- =====================================================================

CREATE TABLE IF NOT EXISTS users (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email             text        NOT NULL CHECK (email = lower(email) AND length(email) BETWEEN 3 AND 254),
  name              text        NOT NULL DEFAULT '' CHECK (length(name) <= 100),
  password_hash     text        NOT NULL,
  email_verified_at timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  last_login_at     timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_idx ON users (email);

CREATE TABLE IF NOT EXISTS user_tokens (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  kind        text        NOT NULL CHECK (kind IN ('verify', 'session')),
  token_hash  text        NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL,
  used_at     timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS user_tokens_hash_idx ON user_tokens (token_hash);
CREATE INDEX IF NOT EXISTS user_tokens_user_idx ON user_tokens (user_id, kind);
