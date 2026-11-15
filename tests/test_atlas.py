"""FlameAtlas routes on this domain (/api/v1/atlas/...), tested against a fake FlameAtlas server (httpx.MockTransport)."""
import json
from types import SimpleNamespace

import httpx
import pytest

from app.atlas import AtlasClient

API = "/api/v1/atlas"
HABITATS = [{"id": "iss", "name": "International Space Station", "o2_pct": 21.0, "pressure_kpa": 101.3, "gravity_g": 0.0},
            {"id": "mars_base", "name": "Mars surface base", "o2_pct": 34.0, "pressure_kpa": 56.5, "gravity_g": 0.378}]


class FakeAtlas:
    """Answers like the FlameAtlas API document; records every request it receives."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.mode = "api"          # "api" | "streamlit" | "down"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if self.mode == "flaky":                       # the tunnel drops the first connection, then answers
            self.mode = "api"
            raise httpx.ConnectError("connection reset", request=request)
        if self.mode == "streamlit":
            return httpx.Response(200, text="<!doctype html><title>Streamlit</title>", headers={"content-type": "text/html; charset=utf-8"})
        path, body = request.url.path, (json.loads(request.content) if request.content and "json" in request.headers.get("content-type", "") else None)
        if path == "/habitats":
            return httpx.Response(200, json=HABITATS)
        if path == "/fuels":
            return httpx.Response(200, json=["Dodecane", "Heptane"])
        if path == "/investigation/PSI-99":
            return httpx.Response(200, json={"id": "PSI-99", "acronym": "SAFFIRE-II", "n_experiments": 7})
        if path.startswith("/investigation/"):
            return httpx.Response(404, json={"detail": f"unknown investigation '{path.rsplit('/', 1)[1]}'"})
        if path == "/compare":
            return httpx.Response(200, json=[{"id": i} for i in request.url.params["ids"].split(",")])
        if path == "/rank":
            if body["habitat_id"] == "venus":
                return httpx.Response(404, json={"detail": "unknown habitat 'venus'"})
            return httpx.Response(200, json={"habitat": {"id": body["habitat_id"]}, "received": body, "results": [{"id": "PSI-69", "rank": 1}]})
        if path in ("/ask", "/retrieve", "/predict"):
            return httpx.Response(200, json={"received": body})
        if path.startswith(("/flammap/", "/gaps/")):
            return httpx.Response(200, json={"path": path, "params": dict(request.url.params)})
        if path == "/graph":
            return httpx.Response(200, json={"center": "diluent:helium", "params": dict(request.url.params), "nodes": [], "edges": []})
        if path == "/graph/facts":
            return httpx.Response(200, json={"facts": ["CO2 was compared with helium (in FLEX)"], "q": request.url.params["q"]})
        if path == "/materials/upload":
            ctype = request.headers["content-type"]
            return httpx.Response(200, json={"multipart": ctype.startswith("multipart/form-data"), "report": request.url.params.get("report"),
                                             "has_csv": b"id,material" in request.content, "report_url": "/materials/report/sample_1"})
        if path == "/materials/report/sample_1":
            return httpx.Response(200, text="<!doctype html><h1>Materials report</h1>", headers={"content-type": "text/html; charset=utf-8"})
        if path == "/whatif":
            return httpx.Response(200, json={"received": body})
        if path == "/passage":
            return httpx.Response(200, json={"hit": request.url.params["id"], "text": "Row 3: ..."})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture()
def atlas(client):
    """Point the app at the fake FlameAtlas for one test, then restore the real client."""
    fake = FakeAtlas()
    original = client.app.state.atlas
    client.app.state.atlas = AtlasClient(SimpleNamespace(atlas_url="https://atlas.test", atlas_timeout=10), transport=httpx.MockTransport(fake))
    yield fake
    client.app.state.atlas = original


def test_not_configured_is_a_clear_503(client):
    r = client.get(f"{API}/habitats")
    assert r.status_code == 503 and "FLAMEATLAS_URL" in r.json()["message"]
    assert client.get(f"{API}/status").json()["configured"] is False


def test_get_routes_forward_and_cache(client, atlas):
    r = client.get(f"{API}/habitats")
    assert r.status_code == 200 and r.json() == HABITATS
    sent = atlas.requests[0]
    assert sent.url == "https://atlas.test/habitats" and sent.headers["ngrok-skip-browser-warning"] == "1"
    client.get(f"{API}/habitats")
    assert len(atlas.requests) == 1                                   # second call served from the cache
    assert client.get(f"{API}/investigation/PSI-99").json()["acronym"] == "SAFFIRE-II"
    assert client.get(f"{API}/compare", params={"ids": "PSI-69,PSI-99"}).json() == [{"id": "PSI-69"}, {"id": "PSI-99"}]
    assert client.get(f"{API}/passage", params={"id": "PSI-99::936617f3::0002"}).json()["hit"] == "PSI-99::936617f3::0002"
    assert client.get(f"{API}/fuels").json() == ["Dodecane", "Heptane"]
    s = client.get(f"{API}/status").json()
    assert s["configured"] and s["reachable"] and "url" not in s     # the upstream address is never shown


def test_post_routes_forward_exactly_what_was_sent(client, atlas):
    body = {"habitat_id": "mars_base", "priorities": {"flammability": 3, "detection": 2, "suppression": 3, "physics": 1, "closeness": 3}, "orness": 0.5, "top": 2}
    r = client.post(f"{API}/rank", json=body)
    assert r.status_code == 200 and r.json()["received"] == body
    ask = {"question": "Which materials were burned in the SAFFIRE-II experiment?", "habitat": "mars_base", "k": 5, "check": True}
    assert client.post(f"{API}/ask", json=ask).json()["received"] == ask
    assert client.post(f"{API}/retrieve", json={"question": "SAFFIRE-II materials", "mode": "hybrid+rerank"}).json()["received"]["mode"] == "hybrid+rerank"
    assert client.post(f"{API}/predict", json={"habitat_id": "mars_base", "fuel": "Heptane"}).json()["received"] == {"habitat_id": "mars_base", "fuel": "Heptane"}
    assert client.post(f"{API}/predict", json={"fuel": "Heptane", "o2_pct": 21, "pressure_kpa": 101.3}).status_code == 200


def test_bad_input_is_rejected_here_without_calling_flameatlas(client, atlas):
    assert client.post(f"{API}/rank", json={"habitat_id": "mars_base", "priorities": {"beauty": 3}}).status_code == 422
    assert client.post(f"{API}/rank", json={"habitat_id": "mars_base", "pairwise": [[1, 2], [3, 4]]}).status_code == 422
    assert client.post(f"{API}/rank", json={"habitat_id": "mars_base", "orness": 2}).status_code == 422
    assert client.post(f"{API}/ask", json={"question": "x"}).status_code == 422
    assert client.post(f"{API}/ask", json={"question": "fine question", "sneaky": 1}).status_code == 422     # unknown fields refused
    assert client.post(f"{API}/predict", json={"fuel": "Heptane"}).status_code == 422                      # needs o2 + pressure or a habitat
    assert client.get(f"{API}/investigation/../../etc").status_code in (404, 422)
    assert client.get(f"{API}/compare", params={"ids": "PSI-69"}).status_code == 422                       # at least two ids
    assert client.get(f"{API}/passage", params={"id": "../secret"}).status_code == 422
    assert atlas.requests == []


def test_flameatlas_errors_use_this_api_envelope(client, atlas):
    r = client.post(f"{API}/rank", json={"habitat_id": "venus"})
    assert r.status_code == 404 and r.json() == {"error": "not_found", "message": "FlameAtlas: unknown habitat 'venus'",
                                                 "detail": "FlameAtlas: unknown habitat 'venus'"}


def test_blank_platform_and_acronym_are_filled():
    """NASA PSI has no platform or acronym for analysis-only projects; the React dashboard crashed on null."""
    from app.atlas import fill_blanks
    out = fill_blanks([{"id": "PSI-60", "acronym": "", "platform": None, "name": "SPICE data analysis"},
                       {"id": "PSI-69", "acronym": "FLEX", "platform": "ISS"}])
    assert out[0]["platform"] == "Not Applicable" and out[0]["acronym"] == "PSI-60" and out[0]["name"] == "SPICE data analysis"
    assert out[1] == {"id": "PSI-69", "acronym": "FLEX", "platform": "ISS"}
    ranked = fill_blanks({"habitat": {"id": "iss"}, "results": [{"id": "PSI-62", "acronym": None, "platform": None, "rank": 1}]})
    assert ranked["results"][0]["platform"] == "Not Applicable" and ranked["results"][0]["acronym"] == "PSI-62"


def test_root_routes_used_by_the_react_dashboard(client, atlas):
    """The dashboard calls FlameAtlas paths at the root (/habitats, /rank, ...): they reach the same validated routes."""
    assert client.get("/habitats").json() == HABITATS
    assert client.get("/investigation/PSI-99").json()["acronym"] == "SAFFIRE-II"
    assert client.post("/rank", json={"habitat_id": "mars_base", "priorities": {"flammability": 3}}).status_code == 200
    bad = client.post("/rank", json={"habitat_id": "venus"})
    assert bad.status_code == 404 and bad.json()["detail"] == "FlameAtlas: unknown habitat 'venus'"
    assert client.post("/ask", json={"question": "x"}).status_code == 422          # validated here, never forwarded
    assert client.get(f"{API}/investigation/PSI-1").status_code == 404


def test_streamlit_address_and_outage_give_clear_messages(client, atlas):
    atlas.mode = "streamlit"
    r = client.get(f"{API}/fuels")
    assert r.status_code == 502 and "Streamlit" in r.json()["message"]
    atlas.mode = "down"
    r = client.get(f"{API}/investigations")
    assert r.status_code == 503 and "Cannot reach FlameAtlas" in r.json()["message"]
    assert client.get(f"{API}/status").json()["reachable"] is False


def test_simulator_routes(client, atlas):
    """Routes of the dashboard's simulator: flammability map, test gaps and what-if."""
    r = client.get("/flammap/mars_base", params={"fuel": "Heptane", "n": 40})
    assert r.status_code == 200 and r.json() == {"path": "/flammap/mars_base", "params": {"fuel": "Heptane", "n": "40"}}
    assert client.get(f"{API}/gaps/moon_base", params={"n": 6}).json()["params"] == {"n": "6", "explain": "false"}
    w = {"habitat_id": "mars_base", "o2_pct": 30, "pressure_kpa": 56.5, "co2_pct": 0, "he_pct": 0, "fuel": "Heptane"}
    assert client.post("/whatif", json=w).json()["received"] == w
    assert client.post("/whatif", json={"text": "Mars base raises oxygen to 30 %", "explain": True}).status_code == 200
    n = len(atlas.requests)
    assert client.get("/flammap/mars_base", params={"n": 5}).status_code == 422            # FlameAtlas needs n >= 10
    assert client.get("/gaps/..%2Fetc").status_code in (404, 422)
    assert client.post("/whatif", json={"o2_pct": 30}).status_code == 422                 # no habitat and no text
    assert client.post("/whatif", json={"habitat_id": "mars_base", "priorities": {"beauty": 1}}).status_code == 422
    assert len(atlas.requests) == n                                                       # nothing bad was forwarded


def test_knowledge_graph_and_graph_rag(client, atlas):
    r = client.get("/graph", params={"entity": "helium", "types": "material,diluent", "radius": 2, "findings": "true"})
    assert r.status_code == 200 and r.json()["params"] == {"entity": "helium", "types": "material,diluent", "radius": "2", "findings": "true"}
    assert client.get(f"{API}/graph/facts", params={"q": "Which fuels were tested with CO2 and helium?"}).json()["facts"]
    ask = {"question": "Which liquid fuels were tested with both CO2 and helium?", "graph": True}
    assert client.post("/ask", json=ask).json()["received"] == ask
    n = len(atlas.requests)
    assert client.get("/graph", params={"types": "planet"}).status_code == 422
    assert client.get("/graph", params={"radius": 3}).status_code == 422
    assert client.get("/graph", params={"entity": "<script>"}).status_code == 422
    assert client.get("/graph/facts", params={"q": "x"}).status_code == 422
    assert len(atlas.requests) == n


def test_materials_upload_and_report(client, atlas):
    csv = b"id,material,LOI_pct\nM-001,Nomex III fabric,29\n"
    r = client.post("/materials/upload", files={"file": ("materials.csv", csv, "text/csv")})
    assert r.status_code == 200 and r.json() == {"multipart": True, "report": "true", "has_csv": True, "report_url": "/materials/report/sample_1"}
    page = client.get(r.json()["report_url"])                         # the report link works on this site
    assert page.status_code == 200 and "Materials report" in page.text
    assert "script-src" not in page.headers["content-security-policy"] and "sandbox" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "SAMEORIGIN"
    n = len(atlas.requests)
    assert client.post("/materials/upload", files={"file": ("evil.exe", csv, "application/octet-stream")}).status_code == 422
    assert client.post("/materials/upload", files={"file": ("empty.csv", b"  ", "text/csv")}).status_code == 422
    big = b"id,material\n" + b"x" * (5 * 1024 * 1024)
    assert client.post("/materials/upload", files={"file": ("big.csv", big, "text/csv")}).status_code == 413
    assert client.get("/materials/report/..%2F..%2Fetc").status_code in (404, 422)
    assert len(atlas.requests) == n


def test_materials_report_pdf_download(client, atlas, monkeypatch):
    from app import pdf
    seen = []
    monkeypatch.setattr(pdf, "find_browser", lambda: "browser")
    monkeypatch.setattr(pdf, "_render", lambda browser, html: seen.append(html) or b"%PDF-1.4 test")
    pdf._cache.clear()
    r = client.get("/materials/report/sample_1/pdf")                  # root path, as the dashboard calls it
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    assert "content-disposition" not in r.headers                      # Edge blanks fetch() of binary responses that carry one
    assert client.get("/materials/report/sample_1/pdf?download=true").headers["content-disposition"] == 'attachment; filename="sample_1-fire-risk-report.pdf"'
    assert "Materials report" in seen[0]
    assert pdf.prepare("<html><head><title>x</title><script>alert(1)</script></head></html>").count("default-src 'none'") == 1
    assert "<script>" not in pdf.prepare("<html><head><script>alert(1)</script></head></html>")
    monkeypatch.setattr(pdf, "find_browser", lambda: None)
    pdf._cache.clear()
    r = client.get(f"{API}/materials/report/sample_1/pdf")
    assert r.status_code == 503 and "Edge or Google Chrome" in r.json()["message"]
    assert client.get(f"{API}/materials/report/..%2Fx/pdf").status_code in (404, 422)


def test_one_dropped_connection_is_retried(client, atlas):
    atlas.mode = "flaky"
    r = client.get(f"{API}/habitats")
    assert r.status_code == 200 and r.json() == HABITATS and len(atlas.requests) == 2
