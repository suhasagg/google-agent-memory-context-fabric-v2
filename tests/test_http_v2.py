import pytest
from fastapi.testclient import TestClient
from context_fabric.api import app, store
from context_fabric.core import Fabric

@pytest.fixture
def client(monkeypatch,tmp_path):
    monkeypatch.setenv("FABRIC_API_KEY","test-secret")
    monkeypatch.setenv("FABRIC_DB",str(tmp_path/"api.sqlite"))
    store.cache_clear()
    with TestClient(app) as c:yield c
    store().close();store.cache_clear()


def test_health_and_auth(client):
    assert client.get("/health").status_code==200
    assert client.get("/v1/memories").status_code==401
    assert client.get("/v1/memories",headers={"x-api-key":"wrong"}).status_code==401


def test_api_write_search_revise_forget(client):
    headers={"x-api-key":"test-secret"}
    result=client.post("/v1/memories",headers=headers,json={"content":"PostgreSQL migrations use Alembic"})
    assert result.status_code==201,result.text
    mid=result.json()["memory_id"]
    hit=client.post("/v1/search",headers=headers,json={"query":"Alembic"})
    assert hit.status_code==200 and hit.json()["items"][0]["memory_id"]==mid
    changed=client.patch(f"/v1/memories/{mid}",headers=headers,json={"content":"Alembic migrations", "expected_version":1})
    assert changed.json()["version"]==2
    gone=client.post(f"/v1/memories/{mid}/forget",headers=headers,json={"reason":"test"})
    assert gone.status_code==200
    assert client.get(f"/v1/memories/{mid}",headers=headers).status_code==404


def test_http_scope_cannot_impersonate(client):
    h={"x-api-key":"test-secret"}
    result=client.post("/v1/memories",headers=h,json={"content":"private", "scope":{"tenant_id":"other"}})
    assert result.status_code==422
    assert client.get('/viewer').status_code==200


def test_credentials_bind_tenant(monkeypatch,tmp_path):
    import json
    monkeypatch.delenv("FABRIC_API_KEY",raising=False)
    monkeypatch.setenv("FABRIC_CREDENTIALS_JSON",json.dumps({
        "alice-key":{"tenant":"one","agent":"alice"},
        "bob-key":{"tenant":"two","agent":"bob"}
    }))
    monkeypatch.setenv("FABRIC_DB",str(tmp_path/"multi.sqlite"))
    store.cache_clear()
    with TestClient(app) as c:
        assert c.post('/v1/memories',headers={'x-api-key':'alice-key'},json={'content':'tenant one data'}).status_code==201
        assert c.post('/v1/search',headers={'x-api-key':'bob-key'},json={'query':'tenant one'}) .json()['items']==[]
    store().close();store.cache_clear()
