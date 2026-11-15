"""
User accounts: sign up, email verification, sign in and sessions (tables in migrations/102_accounts.sql).

  * Passwords: scrypt (Python standard library), random 16-byte salt, constant-time comparison.
  * Tokens (verification links, sessions): 32 random bytes; only their SHA-256 hash is stored, so a
    database leak does not reveal usable links or sessions.
  * A user must verify their email before they can sign in. Verification links expire after 24 hours.
  * Email goes out over SMTP when SMTP_HOST is set. Otherwise (development) the message, including the
    link, is written to the server log and kept in Mailer.outbox.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import logging
import re
import secrets
import smtplib
import ssl
from collections import deque
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

log = logging.getLogger("fif.accounts")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$")
PASSWORD_MIN, PASSWORD_MAX = 10, 128
VERIFY_HOURS = 24
RESET_MINUTES = 60
PROFILES = ("researcher", "engineer", "student")   # mission profile chosen at sign-up (migration 103)
# OWASP Password Storage Cheat Sheet, scrypt: N=2^15, r=8, p=3 (32 MiB, same cost as its N=2^17/p=1 option but
# lighter on memory). Older hashes (N=2^14, p=1) keep working and are upgraded at the next successful login.
_SCRYPT = {"n": 2 ** 15, "r": 8, "p": 3, "dklen": 32}


class AccountError(Exception):
    """An error shown to the user: status code, machine code and a plain message."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# ---------------------------------------------------------------- passwords and tokens
def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, maxmem=64 * 1024 * 1024, **_SCRYPT)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    b64 = lambda b: base64.b64encode(b).decode()
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${b64(salt)}${b64(_scrypt(password, salt))}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt" or not (2 ** 10 <= int(n) <= 2 ** 20) or not (1 <= int(r) <= 32) or not (1 <= int(p) <= 16):
            return False   # refuse malformed or absurd parameters (a tampered row must not exhaust memory)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(base64.b64decode(digest)), maxmem=256 * 1024 * 1024)
        return hmac.compare_digest(got, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def needs_rehash(stored: str) -> bool:
    """True when a stored hash uses older (weaker) scrypt parameters than the current ones."""
    try:
        algo, n, r, p, *_ = stored.split("$")
        return algo != "scrypt" or (int(n), int(r), int(p)) != (_SCRYPT["n"], _SCRYPT["r"], _SCRYPT["p"])
    except ValueError:
        return True


_DUMMY_HASH = hash_password(secrets.token_hex(16))  # equalizes timing when the email is unknown


def new_token() -> tuple[str, str]:
    """(token for the user, SHA-256 hash for the database)."""
    t = secrets.token_urlsafe(32)
    return t, token_hash(t)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e):
        raise AccountError(422, "invalid_email", "Enter a valid email address.")
    return e


def validate_password(pw: str) -> None:
    if len(pw) < PASSWORD_MIN:
        raise AccountError(422, "weak_password", f"Use at least {PASSWORD_MIN} characters for your password.")
    if len(pw) > PASSWORD_MAX:
        raise AccountError(422, "weak_password", f"Use at most {PASSWORD_MAX} characters for your password.")
    if pw.isdigit() or pw.isalpha() and pw.lower() == pw:
        raise AccountError(422, "weak_password", "Mix letters with numbers, symbols or capitals in your password.")


# ---------------------------------------------------------------- email
class Mailer:
    def __init__(self, settings):
        self.s = settings
        self.outbox: deque = deque(maxlen=50)   # development mode only (no SMTP_HOST)

    @property
    def mode(self) -> str:
        return "smtp" if self.s.smtp_host else "log"

    async def send(self, to: str, subject: str, text: str, html_body: str) -> str:
        if not self.s.smtp_host:
            self.outbox.append({"to": to, "subject": subject, "text": text})
            log.warning("SMTP_HOST is not set, so this email was not sent. To: %s | %s\n%s", to, subject, text)
            return "log"
        msg = EmailMessage()
        msg["From"] = self.sender()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html_body, subtype="html")
        await asyncio.to_thread(self._smtp_send, msg)
        return "smtp"

    def sender(self) -> str:
        """SMTP_FROM may be 'Name <addr>', just an address, or just a display name (then SMTP_USER is the address)."""
        name, addr = parseaddr(self.s.smtp_from or "")
        if "@" not in addr:                       # e.g. SMTP_FROM=Flame in Freefall
            name, addr = (self.s.smtp_from or "").strip(), self.s.smtp_user
        return formataddr((name, addr)) if name else addr

    def _smtp_send(self, msg: EmailMessage) -> None:
        s = self.s
        ctx = ssl.create_default_context()
        if s.smtp_security == "ssl":
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ctx, timeout=20)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
        try:
            if s.smtp_security == "starttls":
                server.starttls(context=ctx)
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except smtplib.SMTPException:
                pass


def _mission_email(*, subject: str, preheader: str, heading: str, hello: str, intro: str, button: str, link: str,
                   expiry: str, ignore_note: str, role: str = "", icon: str = "&#10022;") -> str:
    """HTML email in the React dashboard's design (navy #050A2B, card #0C1450, periwinkle #7C9CFF, amber #FFB454).
    Centered layout with one big button; the raw link is never shown (only the button carries it).
    Email-client-safe: tables and inline styles only."""
    e = html.escape
    badge = (f'<tr><td align="center" style="padding-top:16px"><span style="display:inline-block;padding:5px 14px;border-radius:999px;background:#070E3A;'
             f'border:1px solid #7C9CFF;color:#7C9CFF;font-size:13px;font-weight:600">Mission profile: {e(role)}</span></td></tr>') if role else ""
    star = 'style="color:#7C9CFF;font-size:14px;letter-spacing:10px"'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark light"><title>{e(subject)}</title></head>
<body style="margin:0;padding:0;background:#050A2B;font-family:Inter,'Segoe UI',Arial,sans-serif;color:#EEF0FF">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#050A2B"><tr><td align="center" style="padding:36px 14px 44px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px">
    <tr><td align="center" style="padding:0 4px 22px">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td valign="middle" align="center" width="44" height="44" style="width:44px;height:44px;border-radius:50%;background:#0B3D91;font-family:'Space Grotesk',Arial,sans-serif;font-size:12px;font-weight:700;font-style:italic;color:#ffffff;border-bottom:3px solid #FC3D21">NASA</td>
        <td valign="middle" style="padding-left:12px;font-family:'Space Grotesk',Inter,Arial,sans-serif;font-size:16px;font-weight:700;letter-spacing:.02em;color:#EEF0FF">Nasa flame smart detection</td>
      </tr></table>
    </td></tr>
    <tr><td align="center" style="background:#0C1450;border:1px solid #2A3690;border-radius:20px;padding:40px 32px 38px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center"><span {star}>&#10022; &#10023; &#10022;</span></td></tr>
        <tr><td align="center" style="padding-top:14px">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr><td align="center" valign="middle" width="84" height="84"
            style="width:84px;height:84px;border-radius:50%;background:#070E3A;border:2px solid #FFB454;font-size:38px;line-height:84px">{icon}</td></tr></table>
        </td></tr>
        <tr><td align="center" style="padding-top:22px;font-family:'Space Grotesk',Inter,Arial,sans-serif;font-size:28px;line-height:1.25;font-weight:700;color:#EEF0FF">{e(heading)}</td></tr>
        <tr><td align="center" style="padding-top:18px;font-size:17px;line-height:1.6;color:#EEF0FF">{e(hello)}</td></tr>
        <tr><td align="center" style="padding:8px 8px 0;font-size:16px;line-height:1.65;color:#A3A7D8">{e(intro)}</td></tr>
        {badge}
        <tr><td align="center" style="padding-top:32px">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr><td align="center" style="border-radius:14px;background:#FFB454;box-shadow:0 8px 24px rgba(255,180,84,.35)">
            <a href="{e(link)}" style="display:inline-block;padding:20px 52px;font-family:'Space Grotesk',Inter,Arial,sans-serif;font-size:19px;font-weight:700;color:#2A1600;text-decoration:none;border-radius:14px">{e(button)}</a>
          </td></tr></table>
        </td></tr>
        <tr><td align="center" style="padding-top:18px;font-size:14px;color:#A3A7D8">&#9201;&nbsp; {e(expiry)}</td></tr>
        <tr><td align="center" style="padding-top:26px"><span {star}>&#10022; &#10023; &#10022;</span></td></tr>
      </table>
    </td></tr>
    <tr><td align="center" style="padding:20px 10px 0;font-size:13px;line-height:1.6;color:#A3A7D8">{e(ignore_note)}<br><span style="color:#6E74B0">Nasa flame smart detection &middot; NASA Space Apps Challenge 2026 project</span></td></tr>
  </table>
</td></tr></table>
</body></html>"""


def verification_email(name: str, link: str, profile: str = "") -> tuple[str, str, str]:
    """Subject, plain text and HTML of the verification email."""
    hello = f"Hello {name}," if name else "Hello, crew member,"
    role = {"researcher": "Researcher", "engineer": "Engineer", "student": "Student"}.get(profile, "")
    subject = "Confirm your email to join the mission · Nasa flame smart detection"
    text = (f"{hello}\n\nWelcome to Nasa flame smart detection{f' as a {role}' if role else ''}. Confirm your email address to activate your account:\n\n"
            f"{link}\n\nThis link expires in {VERIFY_HOURS} hours. If you did not register, you can ignore this email.\n\n"
            "Nasa flame smart detection · NASA Space Apps Challenge 2026\n")
    body = _mission_email(subject=subject, preheader=f"Confirm your email to activate your account. The link expires in {VERIFY_HOURS} hours.",
                          heading="Confirm your email & join the mission", hello=hello,
                          intro="Welcome aboard. Click the button below to confirm your email address and activate your account.",
                          button="Verify my email", link=link, icon="&#9993;&#65039;", expiry=f"This link expires in {VERIFY_HOURS} hours.",
                          ignore_note="If you did not register, you can safely ignore this email; no account will be activated.", role=role)
    return subject, text, body


def reset_email(name: str, link: str) -> tuple[str, str, str]:
    """Subject, plain text and HTML of the password-reset email."""
    hello = f"Hello {name}," if name else "Hello, crew member,"
    subject = "Reset your password · Nasa flame smart detection"
    text = (f"{hello}\n\nSomeone (hopefully you) asked to reset the password of your Nasa flame smart detection account. Choose a new password here:\n\n"
            f"{link}\n\nThis link expires in {RESET_MINUTES} minutes and works once. If you did not ask for this, ignore this email: "
            "your password stays the same.\n\nNasa flame smart detection · NASA Space Apps Challenge 2026\n")
    body = _mission_email(subject=subject, preheader=f"Choose a new password. The link expires in {RESET_MINUTES} minutes.",
                          heading="Reset your password", hello=hello,
                          intro="We received a request to reset the password of your account. Click the button below to choose a new one.",
                          button="Reset my password", link=link, icon="&#128273;", expiry=f"This link expires in {RESET_MINUTES} minutes and works once.",
                          ignore_note="If you did not ask for a password reset, ignore this email: your password stays the same.")
    return subject, text, body


# ---------------------------------------------------------------- account operations
def _public_user(row: dict) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "profile": row.get("profile", "researcher"),
            "verified": row["email_verified_at"] is not None,
            "createdAt": row["created_at"].isoformat() if row.get("created_at") else None}


class Accounts:
    def __init__(self, services, mailer: Mailer):
        self.s = services
        self.mailer = mailer

    @property
    def pool(self):
        return self.s.pool

    async def _send_verification(self, c, user: dict, base_url: str) -> str:
        # Earlier links stay valid until they expire, so any verification email the person opens works.
        token, h = new_token()
        await c.execute("INSERT INTO user_tokens (user_id, kind, token_hash, expires_at) VALUES (%s, 'verify', %s, now() + make_interval(hours => %s))",
                        (user["id"], h, VERIFY_HOURS))
        link = f"{base_url.rstrip('/')}/api/v1/auth/verify?token={token}"
        return await self.mailer.send(user["email"], *verification_email(user["name"], link, user.get("profile", "")))

    async def signup(self, email: str, name: str, password: str, base_url: str, profile: str = "researcher") -> dict:
        if profile not in PROFILES:
            raise AccountError(422, "invalid_profile", "Choose a mission profile: Researcher, Engineer or Student.")
        email = normalize_email(email)
        name = " ".join((name or "").split())[:100]
        validate_password(password)
        pw_hash = await asyncio.to_thread(hash_password, password)
        async with self.pool.connection() as c, c.transaction():
            row = await (await c.execute(
                "INSERT INTO users (email, name, password_hash, profile) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING "
                "RETURNING id, email, name, profile, email_verified_at, created_at", (email, name, pw_hash, profile))).fetchone()
            if not row:
                raise AccountError(409, "email_taken", "An account with this email already exists. Sign in, or ask for a new verification email.")
            delivery = await self._send_verification(c, row, base_url)
        return {"user": _public_user(row), "emailDelivery": delivery}

    async def resend(self, email: str, base_url: str) -> dict:
        """Same answer whether or not the address exists, so the endpoint cannot be used to discover accounts."""
        try:
            email = normalize_email(email)
        except AccountError:
            return {"sent": True, "emailDelivery": self.mailer.mode}
        async with self.pool.connection() as c, c.transaction():
            row = await (await c.execute("SELECT id, email, name, profile, email_verified_at FROM users WHERE email = %s", (email,))).fetchone()
            if row and row["email_verified_at"] is None:
                await self._send_verification(c, row, base_url)
        return {"sent": True, "emailDelivery": self.mailer.mode}

    async def verify(self, token: str) -> dict:
        async with self.pool.connection() as c, c.transaction():
            t = await (await c.execute(
                "SELECT t.id, t.user_id, t.expires_at < now() AS expired, t.used_at IS NOT NULL AS used, u.email_verified_at "
                "FROM user_tokens t JOIN users u ON u.id = t.user_id WHERE t.token_hash = %s AND t.kind = 'verify' FOR UPDATE OF t",
                (token_hash(token),))).fetchone()
            if not t:
                raise AccountError(400, "invalid_token", "This verification link is not valid.")
            if t["email_verified_at"] is not None:
                return {"verified": True, "already": True}
            if t["used"] or t["expired"]:
                raise AccountError(400, "expired_token", "This verification link has expired. Ask for a new one.")
            await c.execute("UPDATE user_tokens SET used_at = now() WHERE id = %s", (t["id"],))
            await c.execute("UPDATE users SET email_verified_at = now() WHERE id = %s", (t["user_id"],))
        return {"verified": True, "already": False}

    async def login(self, email: str, password: str) -> tuple[str, dict]:
        try:
            email = normalize_email(email)
        except AccountError:
            email = ""
        async with self.pool.connection() as c:
            row = await (await c.execute("SELECT id, email, name, profile, password_hash, email_verified_at, created_at FROM users WHERE email = %s",
                                         (email,))).fetchone() if email else None
        ok = await asyncio.to_thread(check_password, password, row["password_hash"] if row else _DUMMY_HASH)
        if not row or not ok:
            raise AccountError(401, "bad_credentials", "Wrong email or password.")
        if row["email_verified_at"] is None:
            raise AccountError(403, "email_not_verified", "Verify your email first: open the link we sent you, or ask for a new one.")
        new_hash = await asyncio.to_thread(hash_password, password) if needs_rehash(row["password_hash"]) else None
        token, h = new_token()
        async with self.pool.connection() as c, c.transaction():
            if new_hash:   # upgrade an old hash to the current scrypt parameters (the password is known only now)
                await c.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, row["id"]))
            await c.execute("INSERT INTO user_tokens (user_id, kind, token_hash, expires_at) VALUES (%s, 'session', %s, now() + make_interval(days => %s))",
                            (row["id"], h, self.s.settings.session_days))
            await c.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row["id"],))
            # Housekeeping: drop this user's expired or revoked sessions and links.
            await c.execute("DELETE FROM user_tokens WHERE user_id = %s AND (expires_at < now() - interval '7 days' OR (kind = 'session' AND used_at IS NOT NULL))",
                            (row["id"],))
        return token, _public_user(row)

    async def session_user(self, token: str) -> dict | None:
        if not token or len(token) > 200:
            return None
        async with self.pool.connection() as c:
            row = await (await c.execute(
                "SELECT u.id, u.email, u.name, u.profile, u.email_verified_at, u.created_at FROM user_tokens t JOIN users u ON u.id = t.user_id "
                "WHERE t.token_hash = %s AND t.kind = 'session' AND t.used_at IS NULL AND t.expires_at > now()", (token_hash(token),))).fetchone()
        return _public_user(row) if row else None

    async def logout(self, token: str) -> None:
        if token:
            async with self.pool.connection() as c:
                await c.execute("UPDATE user_tokens SET used_at = now() WHERE token_hash = %s AND kind = 'session'", (token_hash(token),))

    # ------------------------------------------------------------ password reset
    async def forgot(self, email: str, base_url: str) -> dict:
        """Email a one-time reset link (60 minutes). Same answer whether or not the account exists."""
        try:
            email = normalize_email(email)
        except AccountError:
            return {"sent": True, "emailDelivery": self.mailer.mode}
        async with self.pool.connection() as c, c.transaction():
            row = await (await c.execute("SELECT id, email, name FROM users WHERE email = %s", (email,))).fetchone()
            if row:
                # Only the newest reset link works: a reset link is powerful, so older ones are cancelled.
                await c.execute("UPDATE user_tokens SET used_at = now() WHERE user_id = %s AND kind = 'reset' AND used_at IS NULL", (row["id"],))
                token, h = new_token()
                await c.execute("INSERT INTO user_tokens (user_id, kind, token_hash, expires_at) VALUES (%s, 'reset', %s, now() + make_interval(mins => %s))",
                                (row["id"], h, RESET_MINUTES))
                link = f"{base_url.rstrip('/')}/reset-password?token={token}"
                await self.mailer.send(row["email"], *reset_email(row["name"], link))
        return {"sent": True, "emailDelivery": self.mailer.mode}

    async def check_reset(self, token: str) -> bool:
        async with self.pool.connection() as c:
            r = await (await c.execute("SELECT 1 FROM user_tokens WHERE token_hash = %s AND kind = 'reset' AND used_at IS NULL AND expires_at > now()",
                                       (token_hash(token),))).fetchone()
        return bool(r)

    async def reset_password(self, token: str, password: str) -> dict:
        """Set a new password. Uses the link once, verifies the email (the link proves the inbox) and signs out every session."""
        validate_password(password)
        pw_hash = await asyncio.to_thread(hash_password, password)
        async with self.pool.connection() as c, c.transaction():
            t = await (await c.execute(
                "SELECT id, user_id, expires_at < now() AS expired, used_at IS NOT NULL AS used FROM user_tokens "
                "WHERE token_hash = %s AND kind = 'reset' FOR UPDATE", (token_hash(token),))).fetchone()
            if not t:
                raise AccountError(400, "invalid_token", "This reset link is not valid. Ask for a new one.")
            if t["used"] or t["expired"]:
                raise AccountError(400, "expired_token", "This reset link has expired or was already used. Ask for a new one.")
            await c.execute("UPDATE user_tokens SET used_at = now() WHERE id = %s", (t["id"],))
            await c.execute("UPDATE users SET password_hash = %s, email_verified_at = coalesce(email_verified_at, now()) WHERE id = %s",
                            (pw_hash, t["user_id"]))
            await c.execute("UPDATE user_tokens SET used_at = now() WHERE user_id = %s AND kind IN ('session', 'reset') AND used_at IS NULL",
                            (t["user_id"],))
            email = (await (await c.execute("SELECT email FROM users WHERE id = %s", (t["user_id"],))).fetchone())["email"]
        return {"reset": True, "email": email}
