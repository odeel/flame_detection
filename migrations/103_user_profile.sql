-- =====================================================================
-- Flame in Freefall, FastAPI backend: PostgreSQL migration 103 (mission profile)
--
-- Each account picks a mission profile when it registers: researcher, engineer or student.
-- Accounts created before this migration become 'researcher'. Idempotent.
-- =====================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS profile text NOT NULL DEFAULT 'researcher';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_profile_check') THEN
    ALTER TABLE users ADD CONSTRAINT users_profile_check CHECK (profile IN ('researcher', 'engineer', 'student'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS users_profile_idx ON users (profile);
