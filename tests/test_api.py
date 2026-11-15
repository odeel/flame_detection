"""API tests against PostgreSQL with real NASA PSI data (seeded from the committed snapshot)."""
import json
from pathlib import Path

from conftest import ADMIN

API = "/api/v1"


def test_health_and_counts(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    d = r.json()
    assert d["data"]["investigations"] == 24 and d["data"]["points"] == 2009
    assert d["data"]["test_rows"] >= 1900
    assert "101_flameatlas.sql" in d["database"]["migrations"]
    assert r.headers["x-request-id"]


def test_habitats(client):
    d = client.get(f"{API}/habitats").json()
    ids = [h["id"] for h in d["items"]]
    assert ids == ["spacecraft", "station", "moonbase", "rover", "marsbase", "spacesuit"]
    moon = next(h for h in d["items"] if h["id"] == "moonbase")
    assert moon["o2"] == 30 and moon["pressure"] == 70.3
    spacesuit = next(h for h in d["items"] if h["id"] == "spacesuit")
    assert spacesuit["evidence"]["investigationsAtAtmosphere"] == 0  # real gap: no PSI test at 100% O2


def test_rank_moonbase_explains_every_score(client):
    d = client.post(f"{API}/rank", json={"habitat": "moonbase", "limit": 5}).json()
    assert d["weights"]["atmosphere"] == 0.4
    top = d["items"][0]
    assert top["components"]["atmosphere"] == 1.0 and top["reasons"]
    assert [i["rank"] for i in d["items"]] == [1, 2, 3, 4, 5]
    scores = [i["score"] for i in d["items"]]
    assert scores == sorted(scores, reverse=True)


def test_rank_weights_and_filters(client):
    a = client.post(f"{API}/rank", json={"habitat": "station", "weights": {"atmosphere": 0, "topic": 0, "data": 0, "gravity": 0, "ventilation": 0, "scale": 1}}).json()
    assert a["items"][0]["accession"] in {"PSI-98", "PSI-99", "PSI-100"}  # Saffire: spacecraft-scale fires
    b = client.post(f"{API}/rank", json={"pillar": "detection", "limit": 50}).json()
    assert b["items"] and all("detection" in i["pillars"] for i in b["items"])
    assert client.post(f"{API}/rank", json={"habitat": "venus"}).status_code == 422
    assert client.post(f"{API}/rank", json={"bogus": 1}).status_code == 422


def test_tests_filters(client):
    eth = client.get(f"{API}/tests", params={"fuel": "ethylene", "o2_min": 30, "limit": 5}).json()
    assert eth["total"] > 100 and all(r["o2Pct"] >= 30 for r in eth["items"])
    assert all(r["fuel"].lower() in ("c2h4", "ethylene") or "c2h4" in r["fuel"].lower() for r in eth["items"])
    co2 = client.get(f"{API}/tests", params={"diluent": "CO2", "accession": "PSI-69", "limit": 1}).json()
    assert co2["total"] > 0 and "CO2" in co2["items"][0]["diluents"]
    near = client.get(f"{API}/tests", params={"o2": 30, "o2_tol": 3, "pressure_max": 90.3, "pressure_min": 50.3}).json()
    assert near["total"] > 0
    f = client.get(f"{API}/tests/facets").json()
    assert f["summary"]["rows"] >= 1900 and f["fuels"]


def test_tests_csv_streams(client):
    r = client.get(f"{API}/tests.csv", params={"accession": "PSI-69"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("accession,acronym") and len(lines) > 200


def test_ask_is_cited_and_grounded(client):
    d = client.post(f"{API}/ask", json={"question": "How does helium or carbon dioxide dilution affect droplet flame extinction?"}).json()
    assert d["answer"] and d["citations"]
    assert d["generator"] == "extractive-v1"  # no API key in tests
    assert d["unverifiedNumbers"] == []
    for c in d["citations"]:
        assert c["accession"].startswith("PSI-") and c["url"].startswith("https://psi.nasa.gov/")
    assert client.post(f"{API}/ask", json={"question": "x"}).status_code == 422


def test_brief_formats(client):
    j = client.get(f"{API}/brief/moonbase").json()
    assert j["habitat"]["id"] == "moonbase" and j["investigations"] and j["gaps"]
    assert any("partial-gravity" in g for g in j["gaps"])
    md = client.get(f"{API}/brief/moonbase", params={"format": "md"})
    assert md.headers["content-type"].startswith("text/markdown") and md.text.startswith("# Fire-safety brief: Lunar surface base")
    html = client.get(f"{API}/brief/spacesuit", params={"format": "html"})
    assert html.status_code == 200 and "<h1>Fire-safety brief: Spacesuit" in html.text


def test_investigation_detail_and_summaries(client):
    d = client.get(f"{API}/investigations/PSI-69").json()
    assert d["record"]["acronym"] == "FLEX" and d["summary"]["generator"] == "extractive-v1"
    assert d["testEnvelope"]["n"] > 200 and set(d["habitats"]) == {"spacecraft", "station", "moonbase", "rover", "marsbase", "spacesuit"}
    assert client.get(f"{API}/investigations/PSI-99999").status_code == 404
    assert client.get(f"{API}/investigations/nope").status_code == 422
    s = client.get(f"{API}/summaries/PSI-159").json()
    assert s["items"][0]["content"]["summary"]


def test_documents_listing(client):
    d = client.get(f"{API}/documents", params={"kind": "metadata"}).json()
    assert d["total"] == 24 and all(x["passages"] > 0 for x in d["items"])


def test_etag_and_errors(client):
    r = client.get(f"{API}/habitats")
    tag = r.headers["etag"]
    assert client.get(f"{API}/habitats", headers={"If-None-Match": tag}).status_code == 304
    e = client.get(f"{API}/nothing-here")
    assert e.status_code == 404 and e.json()["error"] == "not_found"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_admin_requires_token(client):
    assert client.post(f"{API}/admin/cache/clear", headers={"Authorization": "Bearer wrong-key"}).status_code == 401
    assert client.post(f"{API}/admin/cache/clear").status_code in (401, 403)
    assert client.post(f"{API}/admin/cache/clear", headers=ADMIN).status_code == 200
    assert client.get(f"{API}/admin/jobs", headers=ADMIN).status_code == 200


def test_frozen_openapi_schema_matches_code(client):
    """The API schema is frozen in openapi.json; regenerate it with scripts/export_openapi.py when the API changes on purpose."""
    committed = json.loads((Path(__file__).resolve().parent.parent / "openapi.json").read_text())
    assert client.app.openapi() == committed
