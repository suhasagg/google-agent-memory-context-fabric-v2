"""Security, recovery, retrieval and evaluation regressions for the hardened runtime."""
import json
import os
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from context_fabric.api import app, store
from context_fabric.backup import restore_as_new
from context_fabric.core import Fabric, MemoryInput, Principal
from context_fabric.evaluate import evaluate
from context_fabric.security import (AuthConfigError, AuthenticationFailed,
                                     authenticate, hash_api_key, verify_api_key,
                                     validate_security_config)


def test_pbkdf2_key_roundtrip_and_invalid_payload():
    token = "a-secret-with-min-16-characters"
    digest=hash_api_key(token, salt=b"1234567890abcdef",iterations=100_000)
    assert verify_api_key(token,digest)
    assert not verify_api_key(token+"!",digest)
    assert not verify_api_key(token,"pbkdf2_sha256$100000$bad$bad")
    assert not verify_api_key(token,"invalid")
    assert digest.find(token)==-1


def test_prod_mode_rejects_dev_keys(monkeypatch):
    monkeypatch.setenv("FABRIC_MODE","production")
    monkeypatch.setenv("FABRIC_API_KEY","plaintext")
    with pytest.raises(AuthConfigError,match="plaintext"):
        validate_security_config()


def test_prod_mode_requires_identity_provider(monkeypatch):
    monkeypatch.setenv("FABRIC_MODE","production")
    for key in ("FABRIC_API_KEY","FABRIC_CREDENTIALS_JSON","FABRIC_HASHED_CREDENTIALS_JSON","FABRIC_OIDC_ISSUER"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(AuthConfigError,match="requires"):
        validate_security_config()


def test_hashed_tenant_boundary_and_wrong_key(monkeypatch):
    monkeypatch.setenv("FABRIC_MODE","production")
    monkeypatch.delenv("FABRIC_API_KEY", raising=False)
    monkeypatch.delenv("FABRIC_CREDENTIALS_JSON", raising=False)
    data={"team-a":{"hash":hash_api_key("this-is-a-super-secret-a"),
                    "principal":{"tenant":"a","agent":"writer","roles":["admin"]}},
          "team-b":{"hash":hash_api_key("this-is-a-super-secret-b"),
                    "principal":{"tenant":"b","agent":"reader"}}}
    monkeypatch.setenv("FABRIC_HASHED_CREDENTIALS_JSON",json.dumps(data))
    validate_security_config()
    assert authenticate(api_key="this-is-a-super-secret-a").tenant=="a"
    assert authenticate(api_key="this-is-a-super-secret-b").tenant=="b"
    with pytest.raises(AuthenticationFailed): authenticate(api_key="incorrect-key")
    with pytest.raises(AuthenticationFailed): authenticate(api_key="this-is-a-super-secret-a",bearer="anything")


def test_oidc_requires_https_and_audience(monkeypatch):
    monkeypatch.delenv("FABRIC_API_KEY",raising=False)
    monkeypatch.setenv("FABRIC_OIDC_ISSUER","http://example.test")
    monkeypatch.setenv("FABRIC_OIDC_JWKS_URL","http://example.test/jwks")
    monkeypatch.setenv("FABRIC_OIDC_AUDIENCE","memory")
    with pytest.raises(AuthConfigError,match="https"):
        validate_security_config()


def test_oidc_identity_claims_signature_and_allowlist(monkeypatch):
    import base64
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pub=key.public_key()
    n=pub.public_numbers().n
    # Intercept JWKS fetching so this test is network-free; signature is verified by PyJWT.
    class StaticKeys:
        def __init__(self,*args,**kwargs): pass
        def get_signing_key_from_jwt(self,token):
            from types import SimpleNamespace
            return SimpleNamespace(key=pub)
    monkeypatch.setattr(jwt,"PyJWKClient",StaticKeys)
    monkeypatch.setenv("FABRIC_OIDC_ISSUER","https://idp.example.test/")
    monkeypatch.setenv("FABRIC_OIDC_JWKS_URL","https://idp.example.test/jwks")
    monkeypatch.setenv("FABRIC_OIDC_AUDIENCE","context-fabric")
    monkeypatch.setenv("FABRIC_OIDC_ALLOWED_TENANTS","team-a")
    monkeypatch.setenv("FABRIC_OIDC_ALLOWED_ROLES","tenant_reader")
    monkeypatch.setenv("FABRIC_OIDC_MAX_CLEARANCE","INTERNAL")
    from datetime import datetime,timezone,timedelta
    moment=datetime.now(timezone.utc)
    claims={"iss":"https://idp.example.test/", "aud":"context-fabric", "iat":moment,
            "exp":moment+timedelta(minutes=5), "sub":"employee-123",
            "fabric":{"tenant":"team-a","agent":"adk","roles":["tenant_reader","admin"],"clearance":"INTERNAL"}}
    token=jwt.encode(claims,key,algorithm="RS256")
    result=authenticate(bearer=token)
    assert result.tenant=="team-a"
    assert result.agent=="adk"
    assert result.roles==("tenant_reader",)
    with pytest.raises(AuthenticationFailed): authenticate(bearer=token+"tampered")
    claims["fabric"]["tenant"]="unauthorized"
    with pytest.raises(AuthenticationFailed): authenticate(bearer=jwt.encode(claims,key,algorithm="RS256"))
    claims["fabric"]["tenant"]="team-a"
    claims["fabric"]["clearance"]="RESTRICTED"
    with pytest.raises(AuthenticationFailed): authenticate(bearer=jwt.encode(claims,key,algorithm="RS256"))


def test_private_sqlite_and_consistent_backup_restore(tmp_path):
    db=Fabric(tmp_path/"live.sqlite")
    p=Principal(tenant="acme",agent="service")
    mid=db.write(p,MemoryInput(content="confidential order policy"))["memory_id"]
    assert stat.S_IMODE((tmp_path/"live.sqlite").stat().st_mode)==0o600
    backup=tmp_path/"snap.sqlite"
    report=db.backup(backup)
    assert report["integrity"]=="ok"
    with pytest.raises(FileExistsError):db.backup(backup)
    restored=tmp_path/"restored.sqlite"
    assert restore_as_new(backup,restored)["integrity"]=="ok"
    assert stat.S_IMODE(restored.stat().st_mode)==0o600
    db.close()
    check=Fabric(restored)
    assert check.get(p,mid)["content"]=="confidential order policy"
    assert check.verify_integrity()["ok"]
    check.close()


def test_search_more_than_500_and_targeted_scope(tmp_path,monkeypatch):
    d=Fabric(tmp_path/"large.sqlite")
    p=Principal(tenant="a",agent="aa")
    for i in range(515):
        scope={"project":"needle"} if i==0 else {"project":"haystack"}
        d.write(p,MemoryInput(content=("obscure mercury migration" if i==0 else f"arbitrary {i} placeholder"),scope=scope))
    found=d.search(p,"obscure mercury migration",scope={"project":"needle"},limit=3)
    assert len(found["items"])==1
    assert found["items"][0]["content"]=="obscure mercury migration"
    assert len(d.search(p,"arbitrary",scope={"project":"haystack"},limit=2)["items"])==2
    monkeypatch.setenv("FABRIC_SEARCH_MAX_CANDIDATES","100")
    with pytest.raises(ValueError,match="too many candidate"):
        d.search(p,"arbitrary")
    d.close()


def test_request_ids_metrics_auth_and_viewer_production(monkeypatch,tmp_path):
    monkeypatch.setenv("FABRIC_MODE","production")
    monkeypatch.delenv("FABRIC_API_KEY",raising=False)
    monkeypatch.delenv("FABRIC_CREDENTIALS_JSON",raising=False)
    monkeypatch.setenv("FABRIC_HASHED_CREDENTIALS_JSON",json.dumps({
        "ops":{"hash":hash_api_key("secure-operator-key-123"),
               "principal":{"tenant":"ops","agent":"control","roles":["admin"]}},
        "user":{"hash":hash_api_key("secure-reader-key-12345"),
                "principal":{"tenant":"ops","agent":"reader"}}
    }))
    monkeypatch.setenv("FABRIC_DB",str(tmp_path/"server.db"))
    store.cache_clear()
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        assert client.get('/ready').status_code==200
        assert client.get('/viewer').status_code==404
        assert client.get('/metrics').status_code==401
        admin={"x-api-key":"secure-operator-key-123"}
        low={"x-api-key":"secure-reader-key-12345"}
        assert client.get('/metrics',headers=low).status_code==403
        assert client.get('/metrics',headers=admin).status_code==200
        response=client.post('/v1/memories',headers={**admin,"x-request-id":"bad <html>"},json={"content":"rule"})
        assert response.status_code==201
        assert response.headers['x-content-type-options']=="nosniff"
        assert response.headers['cache-control']=="no-store"
        assert '<' not in response.headers['x-request-id']
        assert client.post('/v1/memories',headers={**admin,'content-length':'5000000'},content='{}').status_code==413
    store.cache_clear()


def test_evaluation_smoke_fixture():
    file=Path(__file__).parents[1]/'benchmarks'/'fixtures'/'coding-agent-mini.json'
    fixture=json.loads(file.read_text())
    report=evaluate(fixture['documents'],fixture['questions'],k=3)
    assert report['queries']==8 and report['documents']==12
    assert 0 <= report['recall_at_k'] <= 1
    assert len(report['fixture_sha256'])==64


def test_query_mode_validation_and_scoping(tmp_path):
    d=Fabric(tmp_path/'quick.db'); p=Principal(tenant='one',agent='alpha')
    d.write(p,MemoryInput(content='Intelligent network memory caching',scope={'project':'graph'}))
    assert d.search(p,'network',retrieval_mode='lexical')['items']
    assert d.search(p,'network',retrieval_mode='vector')['items']
    with pytest.raises(ValueError,match='retrieval_mode'):d.search(p,'network',retrieval_mode='invalid')
    with pytest.raises(ValueError,match='query'):d.search(p,' ')
    d.close()


def test_hmac_audit_chain_and_tamper_detection(monkeypatch,tmp_path):
    monkeypatch.setenv('FABRIC_AUDIT_HMAC_KEY','a-test-audit-secret-that-is-over-32-bytes')
    db=Fabric(tmp_path/'audit.sqlite')
    p=Principal(tenant='hospital',agent='ops',roles=('admin',))
    db.write(p,MemoryInput(content='architectural decision'))
    db.write(p,MemoryInput(content='review comment'))
    report=db.verify_audit_chain(p)
    assert report['valid'] and report['verified_events']==2
    db._db.execute("UPDATE audit SET action='forged' WHERE id=1")
    assert not db.verify_audit_chain(p)['valid']
    db.close()


def test_hook_opt_in_secret_filter_and_dedup(monkeypatch,tmp_path):
    from context_fabric.hooks import capture_event, extract_event
    db=Fabric(tmp_path/'hooks.sqlite')
    assert extract_event({'prompt':'token=Bearer supersecrettoken123456'}) is None
    assert extract_event({'prompt':'Our secret: s3cr3t'}) is None
    assert extract_event({'tool_output':'dumped AWS keys'}) is None
    assert capture_event({'prompt':'Use pytest for local validation'},db=db)['stored'] is False
    monkeypatch.setenv('FABRIC_AUTO_CAPTURE','1')
    monkeypatch.setenv('FABRIC_PROJECT','reporting')
    monkeypatch.setenv('FABRIC_AGENT','agent-hook')
    once=capture_event({'prompt':'Use pytest for local validation','session_id':'internal-session-id'},db=db)
    twice=capture_event({'prompt':'Use pytest for local validation','session_id':'internal-session-id'},db=db)
    assert once['stored'] and twice['replayed']
    assert len(db.search(Principal(agent='agent-hook'),'pytest',scope={'project':'reporting'})['items'])==1
    db.close()
