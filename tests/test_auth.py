"""Accounts: sign up, verification email, verify link, sign in, session cookie, sign out (test users are deleted afterwards)."""
import re
import secrets

import psycopg
import pytest

from conftest import TEST_DB

API = "/api/v1/auth"
DOMAIN = "pytest.example.org"


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    if TEST_DB:
        with psycopg.connect(TEST_DB) as c:
            c.execute("DELETE FROM users WHERE email LIKE %s", (f"%@{DOMAIN}",))


def new_email() -> str:
    return f"user-{secrets.token_hex(4)}@{DOMAIN}"


def last_link(client, email: str) -> str:
    box = client.app.state.accounts.mailer.outbox
    msg = next(m for m in reversed(box) if m["to"] == email)
    return re.search(r"(/api/v1/auth/verify\?token=\S+)", msg["text"]).group(1)


def test_signup_verify_login_logout(client):
    email, pw = new_email(), "Correct-Horse-42"
    r = client.post(f"{API}/signup", json={"profile": "engineer", "email": email.upper(), "name": "Ada", "password": pw})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == email and r.json()["user"]["verified"] is False
    assert r.json()["emailDelivery"] == "log"          # no SMTP_HOST in tests

    # Not verified yet: sign-in is refused with a clear code.
    r = client.post(f"{API}/login", json={"email": email, "password": pw})
    assert r.status_code == 403 and r.json()["error"] == "email_not_verified"

    link = last_link(client, email)
    r = client.get(link, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/verify-email?status=ok"
    r = client.get(link, follow_redirects=False)       # second click: already verified
    assert r.headers["location"] == "/verify-email?status=already"

    r = client.post(f"{API}/login", json={"email": email, "password": pw})
    assert r.status_code == 200 and r.json()["user"]["verified"] is True
    cookie = r.headers["set-cookie"]
    assert "fif_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()

    me = client.get(f"{API}/me")
    assert me.json()["user"]["email"] == email and me.headers["cache-control"] == "no-store"

    assert client.post(f"{API}/logout").status_code == 200
    assert client.get(f"{API}/me").json()["user"] is None


def test_signup_errors(client):
    email = new_email()
    assert client.post(f"{API}/signup", json={"profile": "engineer", "email": "not-an-email", "password": "Correct-Horse-42"}).json()["error"] == "invalid_email"
    assert client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "short"}).json()["error"] == "weak_password"
    assert client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "onlylowercaseletters"}).json()["error"] == "weak_password"
    assert client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "Correct-Horse-42"}).status_code == 201
    dup = client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "Another-Pass-77"})
    assert dup.status_code == 409 and dup.json()["error"] == "email_taken"


def test_mission_profile_is_saved_and_required(client):
    for profile in ("researcher", "engineer", "student"):
        email = new_email()
        r = client.post(f"{API}/signup", json={"profile": profile, "email": email, "password": "Correct-Horse-42"})
        assert r.status_code == 201 and r.json()["user"]["profile"] == profile
        client.get(last_link(client, email), follow_redirects=False)
        login = client.post(f"{API}/login", json={"email": email, "password": "Correct-Horse-42"})
        assert login.json()["user"]["profile"] == profile
        assert client.get(f"{API}/me").json()["user"]["profile"] == profile
        client.post(f"{API}/logout")
    with psycopg.connect(TEST_DB) as c:   # stored in the database, constrained to the three values
        assert c.execute("SELECT profile FROM users WHERE email = %s", (email,)).fetchone()[0] == "student"
    assert client.post(f"{API}/signup", json={"email": new_email(), "password": "Correct-Horse-42"}).status_code == 422
    bad = client.post(f"{API}/signup", json={"profile": "pilot", "email": new_email(), "password": "Correct-Horse-42"})
    assert bad.status_code == 422 and "profile" in bad.json()["message"]


def test_login_failures_do_not_reveal_accounts(client):
    email = new_email()
    client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "Correct-Horse-42"})
    client.get(last_link(client, email), follow_redirects=False)
    wrong = client.post(f"{API}/login", json={"email": email, "password": "Wrong-Pass-000"})
    unknown = client.post(f"{API}/login", json={"email": new_email(), "password": "Wrong-Pass-000"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_bad_and_resent_links(client):
    r = client.get(f"{API}/verify", params={"token": "x" * 40}, follow_redirects=False)
    assert r.headers["location"] == "/verify-email?status=invalid"
    email = new_email()
    client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "Correct-Horse-42"})
    old = last_link(client, email)
    assert client.post(f"{API}/resend", json={"email": email}).json()["sent"] is True
    assert client.post(f"{API}/resend", json={"email": new_email()}).json()["sent"] is True   # same answer for unknown emails
    new = last_link(client, email)
    assert new != old
    assert client.get(old, follow_redirects=False).headers["location"] == "/verify-email?status=ok"        # older emails still work
    assert client.get(new, follow_redirects=False).headers["location"] == "/verify-email?status=already"


def full_link(client, email: str, kind: str) -> str:
    msg = next(m for m in reversed(client.app.state.accounts.mailer.outbox) if m["to"] == email)
    pattern = r"(\S+/api/v1/auth/verify\?token=\S+)" if kind == "verify" else r"(\S+/reset-password\?token=\S+)"
    return re.search(pattern, msg["text"]).group(1)


def test_links_point_back_to_this_computer_when_used_locally(client):
    """FIF_PUBLIC_URL names the website; on localhost the email links must still reach the local server."""
    settings = client.app.state.services.settings
    old = settings.public_url
    settings.public_url = "http://site-not-live.example"
    try:
        local = new_email()
        client.post(f"{API}/signup", json={"profile": "student", "email": local, "password": "Correct-Horse-42"},
                    headers={"host": "127.0.0.1:8000"})
        assert full_link(client, local, "verify").startswith("http://127.0.0.1:8000/api/v1/auth/verify?token=")
        remote = new_email()
        client.post(f"{API}/signup", json={"profile": "student", "email": remote, "password": "Correct-Horse-42"})
        assert full_link(client, remote, "verify").startswith("http://site-not-live.example/api/v1/auth/verify?token=")
    finally:
        settings.public_url = old


def test_password_reset(client):
    email, old_pw, new_pw = new_email(), "Correct-Horse-42", "Brand-New-Pass-77"
    client.post(f"{API}/signup", json={"profile": "researcher", "email": email, "password": old_pw})
    client.get(last_link(client, email), follow_redirects=False)
    assert client.post(f"{API}/login", json={"email": email, "password": old_pw}).status_code == 200   # a session to revoke

    # Same answer for unknown addresses; a link is mailed only to real accounts.
    assert client.post(f"{API}/forgot", json={"email": new_email()}).json()["sent"] is True
    assert client.post(f"{API}/forgot", json={"email": email}).json()["sent"] is True
    first = full_link(client, email, "reset")
    client.post(f"{API}/forgot", json={"email": email})
    link = full_link(client, email, "reset")
    token, old_token = link.split("token=")[1], first.split("token=")[1]
    assert token != old_token
    assert client.get(f"{API}/reset/check", params={"token": old_token}).json()["valid"] is False   # only the newest reset link works
    assert client.get(f"{API}/reset/check", params={"token": token}).json()["valid"] is True
    assert client.get("/reset", params={"token": token}).status_code == 200

    assert client.post(f"{API}/reset", json={"token": token, "password": "short"}).json()["error"] == "weak_password"
    r = client.post(f"{API}/reset", json={"token": token, "password": new_pw})
    assert r.status_code == 200 and r.json() == {"reset": True, "email": email}
    assert client.get(f"{API}/me").json()["user"] is None                                            # signed out everywhere
    assert client.post(f"{API}/reset", json={"token": token, "password": "Another-Pass-99"}).json()["error"] == "expired_token"  # one use
    assert client.post(f"{API}/login", json={"email": email, "password": old_pw}).status_code == 401
    assert client.post(f"{API}/login", json={"email": email, "password": new_pw}).status_code == 200
    client.post(f"{API}/logout")


def test_old_password_hashes_are_upgraded_at_login(client):
    import base64, hashlib
    email, pw = new_email(), "Correct-Horse-42"
    salt = b"0123456789abcdef"
    old = "scrypt$16384$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(
        hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)).decode()
    with psycopg.connect(TEST_DB) as c:
        c.execute("INSERT INTO users (email, password_hash, email_verified_at) VALUES (%s, %s, now())", (email, old))
    assert client.post(f"{API}/login", json={"email": email, "password": pw}).status_code == 200      # old hash still works
    with psycopg.connect(TEST_DB) as c:
        stored = c.execute("SELECT password_hash FROM users WHERE email = %s", (email,)).fetchone()[0]
    assert stored.startswith("scrypt$32768$8$3$") and stored != old                                 # ...and was upgraded
    client.post(f"{API}/logout")
    assert client.post(f"{API}/login", json={"email": email, "password": pw}).status_code == 200
    client.post(f"{API}/logout")


def test_reset_also_verifies_the_email(client):
    email = new_email()
    client.post(f"{API}/signup", json={"profile": "engineer", "email": email, "password": "Correct-Horse-42"})
    client.post(f"{API}/forgot", json={"email": email})
    token = full_link(client, email, "reset").split("token=")[1]
    assert client.post(f"{API}/reset", json={"token": token, "password": "Brand-New-Pass-77"}).status_code == 200
    assert client.post(f"{API}/login", json={"email": email, "password": "Brand-New-Pass-77"}).json()["user"]["verified"] is True
    client.post(f"{API}/logout")


def test_account_pages_are_served(client):
    for path in ("/login", "/signup"):
        r = client.get(path)
        assert r.status_code == 200 and "acct-form" in r.text
        assert "script-src 'self'" in r.headers["content-security-policy"]


def test_email_links_follow_a_tunnel_when_public_url_is_this_computer(client):
    """Behind ngrok, with FIF_PUBLIC_URL naming 127.0.0.1, links must use the ngrok address the visitor used."""
    from types import SimpleNamespace
    from app.routers.auth import base_url
    settings = client.app.state.services.settings
    old = settings.public_url
    try:
        def req(host):
            return SimpleNamespace(url=SimpleNamespace(hostname=host), base_url=f"https://{host}/",
                                   app=client.app)
        settings.public_url = "http://127.0.0.1:8000"
        assert base_url(req("abc-1.ngrok-free.app")) == "https://abc-1.ngrok-free.app/"
        settings.public_url = "https://flame.example.org"
        assert base_url(req("abc-1.ngrok-free.app")) == "https://flame.example.org"      # a real site still wins
        assert base_url(req("127.0.0.1")) == "https://127.0.0.1/"
    finally:
        settings.public_url = old
