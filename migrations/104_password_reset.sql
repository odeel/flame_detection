-- =====================================================================
-- Flame in Freefall, FastAPI backend: PostgreSQL migration 104 (password reset)
--
-- user_tokens gains a third kind, 'reset': one-time password-reset links (60 minutes, SHA-256 hash only).
-- Idempotent.
-- =====================================================================

ALTER TABLE user_tokens DROP CONSTRAINT IF EXISTS user_tokens_kind_check;
ALTER TABLE user_tokens ADD CONSTRAINT user_tokens_kind_check CHECK (kind IN ('verify', 'session', 'reset'));
