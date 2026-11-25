import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from paw.api.app import create_app
from paw.api.deps import Context
from paw.db.backup import BackupStore
from paw.db.database import Database

TOKEN = "t" * 43
AUTH = {"Authorization": f"Bearer {TOKEN}"}
MEMORY = {"category": "technical_skill", "title": "FastAPI", "content": "Uses FastAPI"}
PROPOSAL = {
    "payload": {"category": "achievement", "title": "P", "content": "Shipped it"},
    "source": {"source_type": "conversation"},
}
MISSING = "00000000-0000-4000-8000-000000000000"


@pytest.fixture
def client(database: Database, store: BackupStore) -> Iterator[TestClient]:
    app = create_app(Context(database, store), TOKEN)
    with TestClient(app, base_url="http://127.0.0.1", headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def routes(client: TestClient) -> list[tuple[str, str]]:
    paths = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    return [(m.upper(), p) for p, methods in paths.items() for m in methods if p != "/health"]


@pytest.mark.parametrize(
    "header", [None, "", "Bearer", "Bearer wrong", f"Basic {TOKEN}", f"Bearer {TOKEN}x", "Bearer é"]
)
def test_every_route_needs_the_token(client: TestClient, header: str | None) -> None:
    found = routes(client)
    assert len(found) >= 20
    for method, path in found:
        headers = {"Authorization": header.encode("utf-8") if header else b""}
        r = client.request(method, path, headers=headers)
        assert (r.status_code, r.json()["error"]["code"]) == (401, "unauthorized"), (method, path)


def test_health_is_public_and_says_nothing_else(client: TestClient) -> None:
    r = client.get("/health", headers={"Authorization": ""})
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_schema_is_not_served(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "", "evil.example:127.0.0.1"])
def test_foreign_host_is_refused(client: TestClient, host: str) -> None:
    assert client.get("/api/memory", headers={"Host": host}).status_code == 403
    assert client.get("/health", headers={"Host": host}).status_code == 403


def test_browser_origin_is_refused(client: TestClient) -> None:
    for origin in ("http://127.0.0.1", "null", "https://evil.example"):
        assert client.get("/api/memory", headers={"Origin": origin}).status_code == 403


def test_body_limits(client: TestClient) -> None:
    r = client.post("/api/memory", content=b"x" * (1024 * 1024 + 1))
    assert r.status_code == 413
    assert client.post("/api/memory", content=iter([b"{}"])).status_code == 411


def test_memory_lifecycle(client: TestClient) -> None:
    r = client.post("/api/memory", json=MEMORY)
    assert r.status_code == 201
    memory = r.json()["data"]
    url = f"/api/memory/{memory['id']}"
    assert memory["sources"][0]["source_type"] == "manual"
    assert [m["id"] for m in client.get("/api/memory", params={"q": "fastapi"}).json()["data"]] == [
        memory["id"]
    ]
    r = client.put(url, json={**MEMORY, "title": "New", "version": 1})
    assert r.json()["data"]["version"] == 2
    r = client.put(url, json={**MEMORY, "version": 1})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "version_conflict"
    assert r.json()["error"]["details"]["current"]["title"] == "New"
    assert client.post(f"{url}/archive").json()["data"]["status"] == "ARCHIVED"
    assert client.post(f"{url}/archive").status_code == 409
    assert client.post(f"{url}/unarchive").json()["data"]["status"] == "CONFIRMED"
    assert len(client.get(f"{url}/history").json()["data"]) == 4
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_proposals(client: TestClient) -> None:
    first = client.post("/api/memory/proposals", json=PROPOSAL).json()["data"]
    assert (first["status"], first["submitted_by"]) == ("PENDING", "user")
    assert client.get("/api/memory").json()["data"] == []
    r = client.post(f"/api/memory/proposals/{first['id']}/approve")
    assert r.status_code == 200 and r.json()["data"]["status"] == "CONFIRMED"
    assert client.post(f"/api/memory/proposals/{first['id']}/reject").status_code == 409
    second = client.post("/api/memory/proposals", json=PROPOSAL).json()["data"]
    assert second["possible_duplicates"] == [r.json()["data"]["id"]]
    edits = {"edits": {"title": "Edited"}}
    r = client.post(f"/api/memory/proposals/{second['id']}/approve", json=edits)
    assert r.json()["data"]["title"] == "Edited"
    pending = client.get("/api/memory/proposals", params={"status": "PENDING"}).json()["data"]
    assert pending == []


def test_proposal_cannot_choose_its_state_or_submitter(client: TestClient) -> None:
    for extra in ({"status": "APPROVED"}, {"submitted_by": "user"}):
        assert client.post("/api/memory/proposals", json={**PROPOSAL, **extra}).status_code == 422


@pytest.mark.parametrize("suffix", ["", "/history"])
def test_missing_and_malformed_ids(client: TestClient, suffix: str) -> None:
    assert client.get(f"/api/memory/{MISSING}{suffix}").status_code == 404
    assert client.get(f"/api/memory/nope{suffix}").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {},
        {**MEMORY, "title": "  "},
        {**MEMORY, "category": "x"},
        {**MEMORY, "extra": 1},
        {**MEMORY, "content": "x" * 20_001},
    ],
)
def test_invalid_memory(client: TestClient, body: dict[str, object]) -> None:
    r = client.post("/api/memory", json=body)
    assert r.status_code == 422 and r.json()["error"]["details"]["fields"]


def test_validation_error_does_not_echo_input(client: TestClient) -> None:
    r = client.post("/api/memory", json={**MEMORY, "category": "canary-secret"})
    assert "canary-secret" not in r.text


def test_bad_cursor(client: TestClient) -> None:
    for cursor in ("x", "!!", "bm90aGluZw=="):
        assert client.get("/api/memory", params={"cursor": cursor}).status_code == 422


def test_paging(client: TestClient) -> None:
    for i in range(3):
        client.post("/api/memory", json={**MEMORY, "title": str(i)})
    page = client.get("/api/memory", params={"limit": 2}).json()
    rest = client.get("/api/memory", params={"limit": 2, "cursor": page["next_cursor"]}).json()
    assert len(page["data"]) == 2 and len(rest["data"]) == 1 and rest["next_cursor"] is None


def test_profile_and_settings(client: TestClient) -> None:
    body = {"display_name": "A", "profile_data": {"Goals": ["AI engineer"]}, "version": 0}
    assert client.put("/api/profile", json=body).json()["data"]["version"] == 1
    assert client.put("/api/profile", json=body).status_code == 409
    assert client.put("/api/settings", json={"theme": "light"}).status_code == 200
    assert client.get("/api/settings").json()["data"] == {"theme": "light"}
    assert client.put("/api/settings", json={"theme": "pink"}).status_code == 422


def test_dashboard_counts_real_rows(client: TestClient) -> None:
    empty = client.get("/api/dashboard").json()["data"]
    assert empty["confirmed_memories"] == 0 and empty["recent_activity"] == []
    client.post("/api/memory", json=MEMORY)
    client.post("/api/memory/proposals", json=PROPOSAL)
    data = client.get("/api/dashboard").json()["data"]
    assert (data["confirmed_memories"], data["pending_proposals"]) == (1, 1)
    assert data["memories_by_category"] == {"technical_skill": 1}
    assert len(data["latest_proposals"]) == 1
    assert len(client.get("/api/activity").json()["data"]) == 2


def test_export(client: TestClient) -> None:
    client.post("/api/memory", json=MEMORY)
    assert client.get("/api/memory/export").json()["data"]["count"] == 1
    r = client.get("/api/memory/export", params={"format": "markdown"})
    assert "### FastAPI" in r.json()["data"]["markdown"]


def test_backup_restore(client: TestClient) -> None:
    client.post("/api/memory", json=MEMORY)
    backup = client.post("/api/backups").json()["data"]
    client.post("/api/memory", json={**MEMORY, "title": "later"})
    r = client.post(f"/api/backups/{backup['id']}/restore")
    assert r.status_code == 200, r.text
    assert len(client.get("/api/memory").json()["data"]) == 1
    ids = [b["id"] for b in client.get("/api/backups").json()["data"]]
    assert r.json()["data"]["safety_backup"] in ids
    assert client.post("/api/backups/nope/restore").status_code == 404


def test_unexpected_error_hides_details(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object) -> None:
        raise RuntimeError("canary-secret")

    monkeypatch.setattr("paw.api.system.build_dashboard", fail)
    r = client.get("/api/dashboard")
    assert r.status_code == 500 and "canary-secret" not in r.text


def test_logs_hold_no_content_or_token(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="paw"):
        client.post("/api/memory", json={**MEMORY, "content": "canary-secret"})
        client.get("/api/memory", params={"q": "canary-secret"})
    text = "".join(str(r.__dict__) for r in caplog.records)
    assert "/api/memory" in text
    assert "canary-secret" not in text and TOKEN not in text


def test_import(client: TestClient) -> None:
    url = "/api/memory/proposals/import"
    item = PROPOSAL["payload"]
    r = client.post(url, json={"items": [item]})
    assert (r.status_code, r.json()["data"]) == (201, {"added": 1, "skipped": 0})
    r = client.post(url, json={"items": [item, {"title": "no"}]})
    assert r.status_code == 422
    for bad in ({}, {"items": []}, [item], {"items": [item], "x": 1}):
        assert client.post(url, json=bad).status_code == 422
    assert len(client.get("/api/memory/proposals").json()["data"]) == 1
