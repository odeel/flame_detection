"""
Account routes (prefix /api/v1/auth): sign up, email verification, sign in, sign out, current user.

The session is an HttpOnly cookie (fif_session, SameSite=Lax, Secure over HTTPS), so page scripts
never see it. Sign-in attempts are rate limited per client IP.
"""
from __future__ import annotations

from typing import Literal

from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..accounts import AccountError

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "fif_session"
NO_STORE = {"Cache-Control": "no-store", "Vary": "Cookie"}


class SignupRequest(BaseModel):
    profile: Literal["researcher", "engineer", "student"] = Field(..., description="Mission profile chosen at registration")
    email: str = Field(..., max_length=254, examples=["ada@example.org"])
    name: str = Field("", max_length=100, examples=["Ada"])
    password: str = Field(..., max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)


class ResendRequest(BaseModel):
    email: str = Field(..., max_length=254)


class ResetRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    password: str = Field(..., max_length=128)


def accounts(req: Request):
    return req.app.state.accounts


LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def base_url(req: Request) -> str:
    """Where links in emails point.

    On this computer (localhost / 127.0.0.1) links point back to the server you are using, so verification and
    reset work while FIF_PUBLIC_URL names a website that is not live yet. Everywhere else FIF_PUBLIC_URL wins
    (falling back to the request address). Safe: a loopback link can only lead to the reader's own machine.
    """
    if (req.url.hostname or "") in LOOPBACK_HOSTS:
        return str(req.base_url)
    public = req.app.state.services.settings.public_url
    # A public URL that only names this computer is no use to a visitor who came through a tunnel (ngrok):
    # links then use the address they came through (ngrok routes by that host name, so it cannot be forged).
    if not public or (urlsplit(public).hostname or "") in LOOPBACK_HOSTS:
        return str(req.base_url)
    return public


def limit(req: Request, bucket: str, share: float = 1.0) -> None:
    """Per-IP limit: FIF_AUTH_RATE_LIMIT_PER_MIN for sign-in, a share of it for sign-up and resend."""
    ip = req.client.host if req.client else "?"
    per_minute = max(1, int(req.app.state.services.settings.auth_rate_limit_per_min * share))
    ok, retry = req.app.state.limiter.check(f"auth-{bucket}:{ip}", limit=per_minute)
    if not ok:
        raise HTTPException(429, f"Too many attempts. Try again in {retry} seconds.")


def fail(e: AccountError) -> JSONResponse:
    return JSONResponse({"error": e.code, "message": e.message}, status_code=e.status, headers=NO_STORE)


@router.post("/signup", status_code=201, summary="Create an account and send a verification email")
async def signup(req: Request, body: SignupRequest):
    limit(req, "signup", 0.5)
    try:
        out = await accounts(req).signup(body.email, body.name, body.password, base_url(req), body.profile)
    except AccountError as e:
        return fail(e)
    return JSONResponse(out, status_code=201, headers=NO_STORE)


@router.post("/resend", summary="Send a new verification email (same answer whether or not the account exists)")
async def resend(req: Request, body: ResendRequest):
    limit(req, "resend", 0.3)
    return JSONResponse(await accounts(req).resend(body.email, base_url(req)), headers=NO_STORE)


@router.get("/verify", summary="Open the link from the verification email; redirects to the 'Email verified' page", response_class=RedirectResponse)
async def verify(req: Request, token: str = Query(..., min_length=10, max_length=200)):
    try:
        r = await accounts(req).verify(token)
        status = "already" if r["already"] else "ok"
    except AccountError as e:
        status = "expired" if e.code == "expired_token" else "invalid"
    return RedirectResponse(f"/verify-email?status={status}", status_code=303, headers=NO_STORE)


@router.get("/links", summary="Where the account pages send people next (login page of the React dashboard or this site)")
async def links(req: Request):
    from ..config import REPO_ROOT
    front = req.app.state.services.settings.frontend_url
    main_ui = (REPO_ROOT / "ui-dist" / "index.html").is_file()     # the React dashboard is served at "/"
    login = front or ("/" if main_ui else "/login")
    return JSONResponse({"loginUrl": login, "signupUrl": login if (front or main_ui) else "/signup",
                         "frontend": bool(front or main_ui), "emailDelivery": accounts(req).mailer.mode}, headers=NO_STORE)


@router.post("/login", summary="Sign in with email and password; sets the session cookie")
async def login(req: Request, body: LoginRequest):
    limit(req, "login")
    try:
        token, user = await accounts(req).login(body.email, body.password)
    except AccountError as e:
        return fail(e)
    r = JSONResponse({"user": user}, headers=NO_STORE)
    r.set_cookie(COOKIE, token, max_age=req.app.state.services.settings.session_days * 86400, httponly=True,
                 secure=req.url.scheme == "https", samesite="lax", path="/")
    return r


@router.post("/forgot", summary="Email a password-reset link (same answer whether or not the account exists)")
async def forgot(req: Request, body: ResendRequest):
    limit(req, "forgot", 0.3)
    return JSONResponse(await accounts(req).forgot(body.email, base_url(req)), headers=NO_STORE)


@router.get("/reset/check", summary="Whether a password-reset link is still valid")
async def reset_check(req: Request, token: str = Query(..., min_length=10, max_length=200)):
    return JSONResponse({"valid": await accounts(req).check_reset(token)}, headers=NO_STORE)


@router.post("/reset", summary="Set a new password with a reset link; signs out every session")
async def reset(req: Request, body: ResetRequest):
    limit(req, "reset", 0.5)
    try:
        out = await accounts(req).reset_password(body.token, body.password)
    except AccountError as e:
        return fail(e)
    r = JSONResponse(out, headers=NO_STORE)
    r.delete_cookie(COOKIE, path="/")
    return r


@router.post("/logout", summary="Sign out (revokes the session)")
async def logout(req: Request):
    await accounts(req).logout(req.cookies.get(COOKIE, ""))
    r = JSONResponse({"signedOut": True}, headers=NO_STORE)
    r.delete_cookie(COOKIE, path="/")
    return r


@router.get("/me", summary="The signed-in user, or null")
async def me(req: Request):
    user = await accounts(req).session_user(req.cookies.get(COOKIE, ""))
    return JSONResponse({"user": user, "emailDelivery": accounts(req).mailer.mode}, headers=NO_STORE)
