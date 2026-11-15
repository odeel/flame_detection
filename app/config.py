"""Settings from environment variables (or backend-fastapi/.env), validated once at startup."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent      # backend-fastapi/
REPO_ROOT = BACKEND_DIR.parent                            # repository root (shared data, base schema)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="", extra="ignore")

    database_url: str = Field("postgres://fif:fif_dev_pw@localhost:5432/fif", alias="DATABASE_URL")
    admin_token: str = Field("", alias="FIF_ADMIN_TOKEN")
    cors_origins: str = Field("", alias="FIF_CORS_ORIGINS")
    # The React dashboard (frontend/, Vite dev server). Bearer tokens, no cookies, so CORS is credential-free.
    frontend_origins: str = Field("http://localhost:5173,http://127.0.0.1:5173", alias="FIF_FRONTEND_ORIGINS")
    # Where "Continue to login" goes after email verification / password reset (e.g. http://localhost:5173 for the
    # React dashboard). Empty = this site's own /login page.
    frontend_url: str = Field("", alias="FIF_FRONTEND_URL")
    # The React dashboard's own folder (the team's frontend, used as it is). start.ps1 builds it from there into
    # <repo>/ui-dist without changing any of its files; the backend serves that build at "/".
    frontend_dir: str = Field("", alias="FIF_FRONTEND_DIR")

    @field_validator("frontend_url")
    @classmethod
    def _frontend_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("FIF_FRONTEND_URL must start with http:// or https://")
        return v
    rate_limit_per_min: int = Field(600, alias="FIF_RATE_LIMIT_PER_MIN", ge=1)
    pool_max: int = Field(10, alias="PG_POOL_MAX", ge=1, le=200)
    documents_dir: Path = Field(BACKEND_DIR / "data" / "psi-docs", alias="FIF_DOCUMENTS_DIR")
    claude_model: str = Field("claude-opus-5-5", alias="FIF_MODEL")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    seed_on_start: bool = Field(True, alias="FIF_SEED_ON_START")
    # Accounts and email verification. With SMTP_HOST empty, verification links are written to the server log.
    public_url: str = Field("", alias="FIF_PUBLIC_URL")            # e.g. https://fire.example.org (links in emails); empty = from the request
    session_days: int = Field(30, alias="FIF_SESSION_DAYS", ge=1, le=365)
    auth_rate_limit_per_min: int = Field(10, alias="FIF_AUTH_RATE_LIMIT_PER_MIN", ge=1)   # sign-in attempts per IP (sign-up and resend use less)
    smtp_host: str = Field("", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT", ge=1, le=65535)
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from: str = Field("", alias="SMTP_FROM")                  # e.g. "Flame in Freefall <no-reply@example.org>"
    smtp_security: str = Field("starttls", alias="SMTP_SECURITY", pattern="^(starttls|ssl|none)$")
    # FlameAtlas API (the team's RAG / AHP ranking / droplet-prediction service), served on this domain under /api/v1/atlas.
    atlas_url: str = Field("", alias="FLAMEATLAS_URL")            # e.g. https://xxxx.ngrok-free.app (the API, not the Streamlit app)
    atlas_timeout: float = Field(60.0, alias="FLAMEATLAS_TIMEOUT", ge=5, le=300)   # /ask can take 10-20 s

    @field_validator("atlas_url")
    @classmethod
    def _atlas(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("FLAMEATLAS_URL must start with http:// or https://")
        return v

    @field_validator("database_url")
    @classmethod
    def _pg(cls, v: str) -> str:
        if not v.startswith(("postgres://", "postgresql://")):
            raise ValueError("DATABASE_URL must look like postgres://user:password@host:5432/database")
        return v

    @field_validator("admin_token")
    @classmethod
    def _token(cls, v: str) -> str:
        if v and len(v) < 16:
            raise ValueError("FIF_ADMIN_TOKEN must be at least 16 characters")
        return v

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def frontend_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
