"""The React dashboard's data contract (frontend/DATA_CONTRACT.md), served under /api/... (app/routers/frontend.py)."""
import re
import secrets

import psycopg
import pytest

from conftest import TEST_DB

DOMAIN = "fe-test.example.org"
PW = "Correct-Horse-42"
INV_KEYS = {"id", "name", "subtitle", "hardware", "platform", "fuelClass", "fuelDetail", "geometry", "objective", "pillar", "gravity", "o2Range",
            "pressureRangePsi", "flowRangeCms", "variables", "sensors", "extinctionNote", "relevanceTags", "earthApplication", "doi", "psiUrl", "dataSizeGB"}
TEST_KEYS = {"testId", "investigationId", "o2Pct", "pressurePsi", "flowCms", "gravity", "fuel", "thicknessMm", "outcome", "spreadRateMmS"}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    if TEST_DB:
        with psycopg.connect(TEST_DB) as c:
            c.execute("DELETE FROM users WHERE email LIKE %s", (f"%@{DOMAIN}",))


def account(client, role="researcher") -> tuple[str, str]:
    """A verified account; returns (email, bearer token)."""
    email = f"{role}-{secrets.token_hex(4)}@{DOMAIN}"
    r = client.post("/api/auth/signup", json={"email": email, "password": PW, "role": role})
    assert r.status_code == 201 and r.json()["token"] is None and r.json()["verificationRequired"] is True
    msg = next(m for m in reversed(client.app.state.accounts.mailer.outbox) if m["to"] == email)
    client.get(re.search(r"(/api/v1/auth/verify\?token=\S+)", msg["text"]).group(1), follow_redirects=False)
    r = client.post("/api/auth/login", json={"email": email, "password": PW, "role": role})
    assert r.status_code == 200, r.text
    client.cookies.clear()                     # use the bearer token only, like the React app
    return email, r.json()["token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_investigations_follow_the_contract(client):
    items = client.get("/api/investigations").json()
    assert len(items) == 28
    for it in items:
        assert INV_KEYS <= set(it), INV_KEYS - set(it)           # every field present (null when unknown, never missing)
        assert it["gravity"] in ("microgravity", "partial", "normal")
        assert set(it["pillar"]) <= {"prevention", "detection", "suppression", "other"}
    bass = next(i for i in items if i["id"] == "bass")
    assert bass["name"] == "BASS" and bass["hardware"] == "MSG" and bass["fuelClass"] == "Solid"
    assert bass["psiUrl"].endswith("/PSI-26") and bass["doi"] and bass["dataSizeGB"] > 1
    flex = next(i for i in items if i["id"] == "flex")
    assert flex["rangesSource"] == "measured" and flex["o2Range"][0] < 21 < flex["o2Range"][1]   # from NASA's FLEX test matrix


def test_tests_of_an_investigation(client):
    rows = client.get("/api/investigations/flex/tests").json()
    assert len(rows) > 200 and TEST_KEYS <= set(rows[0])
    assert all(r["investigationId"] == "flex" and r["gravity"] == "microgravity" for r in rows)
    assert {"extinguished", "steady"} <= {r["outcome"] for r in rows}
    assert any(r["pressurePsi"] and 10 < r["pressurePsi"] < 20 for r in rows)
    saffire = client.get("/api/investigations/saffire-1/tests").json()
    assert any(r["thicknessMm"] == 3.7 for r in saffire)            # "Sample Thickness (cm)": 0.37 -> 3.7 mm
    assert client.get("/api/investigations/sofball/tests").json() == []      # curated only, no PSI test matrix
    r = client.get("/api/investigations/nope/tests")
    assert r.status_code == 404 and r.json() == {"error": "Unknown investigation 'nope'", "code": "not_found"}


def test_habitats_and_kpis(client):
    hs = client.get("/api/habitats").json()
    moon = next(h for h in hs if h["id"] == "moonbase")
    assert moon["o2Pct"] == 30 and moon["pressurePsi"] == 10.2
    for role in ("researcher", "engineer", "student"):
        k = client.get("/api/kpis", params={"role": role}).json()["kpis"]
        assert len(k) == 4 and all(len(p) == 2 and p[0] for p in k)
    assert client.get("/api/kpis", params={"role": "researcher"}).json()["kpis"][1] == ["24", "PSI investigations"]


def test_auth_roles_and_errors(client):
    email, token = account(client, "engineer")
    me = client.get("/api/auth/me", headers=bearer(token)).json()["user"]
    assert me["email"] == email and me["role"] == "engineer"
    wrong_role = client.post("/api/auth/login", json={"email": email, "password": PW, "role": "student"})
    assert wrong_role.status_code == 403 and wrong_role.json()["code"] == "role_mismatch"
    bad = client.post("/api/auth/login", json={"email": email, "password": "nope-nope-nope", "role": "engineer"})
    assert bad.status_code == 401 and "error" in bad.json()
    # An old token must not block logging in again.
    again = client.post("/api/auth/login", json={"email": email, "password": PW, "role": "engineer"}, headers=bearer("stale-token-xxxxxxxxxx"))
    assert again.status_code == 200
    assert client.get("/api/kpis", params={"role": "student"}, headers=bearer(token)).status_code == 403   # role enforced server-side
    assert client.get("/api/conversations").status_code == 401
    client.post("/api/auth/logout", headers=bearer(token))
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_chat_and_conversations(client):
    _, token = account(client, "student")
    other_email, other = account(client, "researcher")
    r = client.post("/api/chat", headers=bearer(token),
                    json={"question": "How does helium or carbon dioxide dilution affect droplet flame extinction?", "conversationId": None,
                          "role": "student", "habitat": "Lunar surface base"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["answer"] and a["citations"] and a["confidence"] in ("high", "medium", "low", "none") and a["followups"]
    assert a["source"] == "local"                                         # FlameAtlas is not configured in tests
    assert all({"investigationId", "title", "snippet", "url"} <= set(c) for c in a["citations"])
    cid = a["conversationId"]
    r2 = client.post("/api/chat", headers=bearer(token), json={"question": "Which suppressants were tested?", "conversationId": cid})
    assert r2.json()["conversationId"] == cid
    convs = client.get("/api/conversations", headers=bearer(token)).json()
    assert convs[0]["id"] == cid and convs[0]["habitat"] == "Lunar surface base" and convs[0]["messages"] == 4
    full = client.get(f"/api/conversations/{cid}", headers=bearer(token)).json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant", "user", "assistant"] and full["messages"][1]["citations"]
    # Another account cannot read, extend or delete it.
    assert client.get(f"/api/conversations/{cid}", headers=bearer(other)).status_code == 404
    assert client.post("/api/chat", headers=bearer(other), json={"question": "Which suppressants were tested?", "conversationId": cid}).status_code == 404
    assert client.delete(f"/api/conversations/{cid}", headers=bearer(other)).status_code == 404
    assert client.post("/api/chat", headers=bearer(token), json={"question": "Which suppressants?", "role": "engineer"}).status_code == 403
    assert client.delete(f"/api/conversations/{cid}", headers=bearer(token)).json()["deleted"] is True
    assert client.get("/api/conversations", headers=bearer(token)).json() == []


def test_chat_exactly_as_the_react_dashboard_sends_it(client):
    """Chatstore.js: no token (demo login), a browser-made conversation id, the dashboard's habitat names."""
    import uuid
    from app.routers.frontend import habitat_id
    assert [habitat_id(h) for h in ("Spacecraft / ISS", "Lunar base / rover", "EVA spacesuit", "Mars base")] == ["station", "moonbase", "spacesuit", "marsbase"]
    cid = str(uuid.uuid4())
    r = client.post("/api/chat", json={"question": "Which tests cover lunar base conditions?", "conversationId": cid, "role": "researcher",
                                       "habitat": "Lunar base / rover"}, headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["conversationId"] == cid and a["saved"] is False and a["answer"] and isinstance(a["citations"], list) and a["followups"]
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    # Signed in, the same browser-made id becomes a saved conversation.
    _, token = account(client, "researcher")
    cid2 = str(uuid.uuid4())
    r = client.post("/api/chat", headers=bearer(token), json={"question": "Is there partial-gravity data?", "conversationId": cid2, "role": "researcher",
                                                             "habitat": "Spacecraft / ISS"})
    assert r.json()["saved"] is True
    assert client.get(f"/api/conversations/{cid2}", headers=bearer(token)).json()["habitat"] == "Spacecraft / ISS"


def test_verification_and_reset_pages_in_the_dashboard_design(client):
    for path in ("/verify-email?status=ok", "/forgot-password", "/reset-password?token=x" + "y" * 20, "/reset?token=" + "z" * 20):
        r = client.get(path)
        assert r.status_code == 200 and "auth-app.js" in r.text and "script-src 'self'" in r.headers["content-security-policy"]
    links = client.get("/api/v1/auth/links").json()
    from app.config import REPO_ROOT
    main_ui = (REPO_ROOT / "ui-dist" / "index.html").is_file()
    assert links["loginUrl"] == ("/" if main_ui else "/login") and links["frontend"] is main_ui   # React UI at "/" when built
    # The emails use the React dashboard's palette (navy card, amber button) and link to the new pages.
    email = f"design-{secrets.token_hex(3)}@{DOMAIN}"
    client.post("/api/auth/signup", json={"email": email, "password": PW, "role": "student"})
    box = client.app.state.accounts.mailer.outbox
    assert "/api/v1/auth/verify?token=" in next(m for m in reversed(box) if m["to"] == email)["text"]
    from app.accounts import verification_email
    _, _, html_body = verification_email("Ada", "https://example.org/x", "student")
    assert "#FFB454" in html_body and "#0C1450" in html_body and "Mission profile: Student" in html_body


def test_forgot_and_reset_for_the_react_app(client):
    email, token = account(client, "engineer")
    assert client.post("/api/auth/forgot", json={"email": f"nobody-{secrets.token_hex(3)}@{DOMAIN}"}).json()["sent"] is True   # same answer
    assert client.post("/api/auth/forgot", json={"email": email}).json()["sent"] is True
    msg = next(m for m in reversed(client.app.state.accounts.mailer.outbox) if m["to"] == email)
    link = re.search(r"(\S+/reset-password\?token=\S+)", msg["text"]).group(1)
    reset_token = link.split("token=")[1]
    assert client.get("/reset-password", params={"token": reset_token}).status_code == 200
    bad = client.post("/api/auth/reset", json={"token": reset_token, "password": "short"})
    assert bad.status_code == 422 and bad.json()["code"] == "weak_password"
    ok = client.post("/api/auth/reset", json={"token": reset_token, "password": "Brand-New-Pass-77"})
    assert ok.status_code == 200 and ok.json() == {"reset": True, "email": email}
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401                 # signed out everywhere
    assert client.post("/api/auth/login", json={"email": email, "password": "Brand-New-Pass-77", "role": "engineer"}).status_code == 200
    again = client.post("/api/auth/reset", json={"token": reset_token, "password": "Another-Pass-99"})
    assert again.status_code == 400 and again.json()["code"] == "expired_token"                    # one use only


def test_main_ui_is_the_react_dashboard(client):
    from app.config import REPO_ROOT
    dist = REPO_ROOT / "ui-dist"
    if not (dist / "index.html").is_file():
        pytest.skip("React dashboard not built (run start.cmd once)")
    home = client.get("/")
    assert home.status_code == 200 and "/ui-assets/" in home.text and "script-src 'self'" in home.headers["content-security-policy"]
    js = re.search(r"/ui-assets/[\w.-]+\.js", home.text).group(0)
    assert client.get(js).status_code == 200
    classic = client.get("/classic")
    assert classic.status_code == 200 and "assets/js/app.js" in classic.text


def test_cors_for_the_vite_dev_server(client):
    r = client.options("/api/investigations", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
                                                       "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.options("/api/conversations/x", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"})
    assert "DELETE" in r.headers["access-control-allow-methods"]
    assert "access-control-allow-origin" not in client.get("/api/habitats", headers={"Origin": "https://evil.example"}).headers
