"""Authenticated HTTP API, local viewer and OpenAPI documentation.

Credentials map API keys to immutable principals. NEVER accept tenant/agent from
an untrusted JSON request. Use an identity provider and TLS proxy in production.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from functools import lru_cache
from threading import Lock

from .core import Fabric, Principal, MemoryInput, Missing, Forbidden, Conflict
from .security import authenticate, AuthenticationFailed, validate_security_config

try:
    from fastapi import FastAPI, Depends, Header, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field, ConfigDict
except ImportError as exc:
    raise ImportError('Install API extras: pip install -e ".[api]"') from exc


class WriteRequest(BaseModel):
    content: str
    layer: str = "semantic"
    scope: dict[str,str] = Field(default_factory=dict)
    classification: str = "INTERNAL"
    confidence: float = 1.0
    source_type: str = "manual"
    source_id: str = "user"
    evidence: dict = Field(default_factory=dict)
    ttl_days: int | None = 90
    purpose: str = "context"
    verified: bool = False
    valid_from: str | None = None
    valid_to: str | None = None


class SearchRequest(BaseModel):
    query: str
    scope: dict[str,str] = Field(default_factory=dict)
    layers: list[str] | None = None
    purpose: str = "context"
    limit: int = 10
    token_budget: int = 2000
    graph_depth: int = 0
    retrieval_mode: str = "hybrid"


class UpdateRequest(BaseModel):
    content: str
    expected_version: int
    reason: str = "revision"
    source_id: str = "manual"


class ForgetRequest(BaseModel):
    reason: str = "user request"


class GrantRequest(BaseModel):
    to_agent: str
    layers: list[str]
    scope: dict[str,str] = Field(default_factory=dict)
    purposes: list[str] = Field(default_factory=lambda:["context"])
    ttl_days: int = 7


class EdgeRequest(BaseModel):
    from_id: str
    to_id: str
    relation: str = "related_to"


class ProfileRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    name: str
    fields: dict
    schema_: dict = Field(alias="schema")
    expected_version: int | None = None


@lru_cache
def store() -> Fabric:
    return Fabric()


def principal(x_api_key: str | None = Header(default=None),
              authorization: str | None = Header(default=None)) -> Principal:
    bearer = None
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required")
        bearer = authorization[7:]
    try:
        return authenticate(api_key=x_api_key, bearer=bearer)
    except AuthenticationFailed:
        raise HTTPException(status_code=401, detail="missing or invalid credential", headers={"WWW-Authenticate":"Bearer"})


@asynccontextmanager
async def lifespan(application):
    validate_security_config()
    instance = store()
    check = instance.verify_integrity()
    if not check["ok"]:
        raise RuntimeError("database integrity check failed")
    yield
    instance.close()
    store.cache_clear()


app=FastAPI(title="Google Agent Memory Context Fabric", version="3.0.0",
            lifespan=lifespan)
METRICS = Counter()
METRICS_LOCK = Lock()


@app.middleware("http")
async def privacy_and_metrics(request: Request, call_next):
    start = time.monotonic()
    rid = request.headers.get("x-request-id", "")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", rid):
        rid = str(uuid.uuid4())
    max_bytes = int(os.getenv("FABRIC_MAX_REQUEST_BYTES", "131072"))
    content_length = request.headers.get("content-length")
    if content_length and (not content_length.isdigit() or int(content_length) > max_bytes):
        response = JSONResponse({"detail": "request body exceeds configured limit"}, status_code=413)
    else:
        response = await call_next(request)
    elapsed = time.monotonic() - start
    route = request.scope.get("route")
    # Do not use raw URL paths, which include memory IDs / user identifiers, as metric labels.
    label = route.path if route is not None else "unmatched"
    if label not in ("/health", "/ready", "/metrics"):
        with METRICS_LOCK:
            METRICS[(request.method, label, response.status_code)] += 1
            METRICS[("latency_ms_total", "all", "sum")] += int(elapsed * 1000)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(Missing)
async def missing_handler(request:Request, exc:Missing):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail":str(exc)},status_code=404)


@app.exception_handler(Forbidden)
async def forbidden_handler(request:Request, exc:Forbidden):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail":str(exc)},status_code=403)


@app.exception_handler(Conflict)
async def conflict_handler(request:Request, exc:Conflict):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail":str(exc)},status_code=409)


@app.exception_handler(ValueError)
async def value_handler(request:Request, exc:ValueError):
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail":str(exc)},status_code=422)


@app.get("/health")
def health():
    return {"status": "alive", "version": "3.0.0"}


@app.get("/ready")
def ready():
    try:
        with store()._lock:
            store()._db.execute("SELECT 1").fetchone()
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="storage unavailable")


@app.get("/metrics")
def metrics(p: Principal = Depends(principal)):
    if not p.can("admin"):
        raise HTTPException(status_code=403, detail="admin required")
    with METRICS_LOCK:
        values = [{"method": k[0], "route": k[1], "status": k[2], "count": v}
                  for k, v in METRICS.items() if k[0] != "latency_ms_total"]
    return {"requests": values, "note": "process-local only; no tenant/request/user identifiers"}



@app.post("/v1/memories",status_code=201)
def create(data:WriteRequest,p:Principal=Depends(principal),idempotency_key:str|None=Header(None)):
    return store().write(p,MemoryInput(**data.model_dump()),idempotency_key)


@app.get("/v1/memories")
def ls(p:Principal=Depends(principal),layer:str|None=None,purpose:str="context",limit:int=100,offset:int=0):
    return {"items":store().list_memories(p,layer=layer,purpose=purpose,limit=limit,offset=offset)}


@app.get("/v1/memories/{memory_id}")
def get(memory_id:str,p:Principal=Depends(principal),purpose:str="context"):
    return store().get(p,memory_id,purpose)


@app.patch("/v1/memories/{memory_id}")
def revise(memory_id:str,data:UpdateRequest,p:Principal=Depends(principal)):
    return store().update(p,memory_id,**data.model_dump())


@app.get("/v1/memories/{memory_id}/history")
def history(memory_id:str,p:Principal=Depends(principal)):
    return {"revisions":store().history(p,memory_id)}


@app.post("/v1/memories/{memory_id}/forget")
def forget(memory_id:str,data:ForgetRequest,p:Principal=Depends(principal)):
    return store().forget(p,memory_id,data.reason)


@app.post("/v1/context")
@app.post("/v1/search")
def search(data:SearchRequest,p:Principal=Depends(principal)):
    return store().search(p,**data.model_dump())


@app.post("/v1/conflicts")
def conflicts(data:WriteRequest,p:Principal=Depends(principal)):
    return {"candidates":store().conflicts(p,data.content,data.scope)}


@app.get("/v1/consolidation/candidates")
def consolidation_candidates(p:Principal=Depends(principal),threshold:float=.85):
    return {"candidates":store().consolidate_candidates(p,threshold=threshold)}


@app.post("/v1/grants")
def grant(data:GrantRequest,p:Principal=Depends(principal)):
    return store().grant(p,**data.model_dump())


@app.post("/v1/grants/{grant_id}/revoke")
def revoke(grant_id:str,p:Principal=Depends(principal)):
    return store().revoke(p,grant_id)


@app.post("/v1/graph/edges")
def edge(data:EdgeRequest,p:Principal=Depends(principal)):
    return store().link(p,**data.model_dump())


@app.get("/v1/graph/{memory_id}/neighbors")
def neighbors(memory_id:str,p:Principal=Depends(principal),depth:int=1,purpose:str="context"):
    return {"items":store().neighbors(p,memory_id,purpose,depth)}


@app.put("/v1/profiles")
def set_profile(data:ProfileRequest,p:Principal=Depends(principal)):
    return store().profile_set(p,**data.model_dump(by_alias=True))


@app.get("/v1/profiles/{name}")
def get_profile(name:str,p:Principal=Depends(principal)):
    return store().profile_get(p,name)


@app.get("/v1/audit")
def audit(p:Principal=Depends(principal),limit:int=100):
    return {"items":store().audit_events(p,limit)}


@app.get("/v1/audit/verify")
def audit_verify(p: Principal = Depends(principal)):
    return store().verify_audit_chain(p)


@app.get("/v1/outbox")
def outbox(p:Principal=Depends(principal),limit:int=100):
    return {"items":store().outbox_events(p,limit)}


@app.post("/v1/maintenance/sweep")
def sweep(p:Principal=Depends(principal)):
    return store().sweep_expired(p)


@app.get("/viewer",response_class=HTMLResponse)
def viewer():
    if os.getenv("FABRIC_MODE") == "production":
        raise HTTPException(status_code=404, detail="local viewer disabled in production")
    # Pure static HTML; credentials only entered locally into this page. No remote assets.
    return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Context Fabric • Memory Explorer</title><style>
body{font:16px system-ui,sans-serif;margin:0;background:#0b1220;color:#e5e7eb}main{max-width:900px;margin:auto;padding:35px}
input,button{font:inherit;padding:12px;border-radius:8px;border:1px solid #4b5563;background:#182236;color:white}
input{width:60%}button{cursor:pointer;background:#2357a8}article{background:#162133;border:1px solid #354052;border-radius:12px;padding:18px;margin:16px 0}
small{color:#9ca3af}pre{white-space:pre-wrap;word-break:break-word}h1{color:#97c2ff}
</style></head><body><main><h1>Context Fabric / Memory Explorer</h1><p>Local-first memory search. API keys are held only in this page's memory.</p>
<p><input id='key' type='password' placeholder='API key' autocomplete='off'></p>
<p><input id='query' placeholder='Search your memories'><button id='go'>Search</button></p>
<div id='result' aria-live='polite'></div></main><script>
document.getElementById('go').onclick=async()=>{const result=document.getElementById('result');result.replaceChildren();
try{const r=await fetch('/v1/search',{method:'POST',headers:{'Content-Type':'application/json','x-api-key':document.getElementById('key').value},
body:JSON.stringify({query:document.getElementById('query').value,limit:20})});if(!r.ok)throw Error('Request failed: '+r.status);
const data=await r.json();for(const m of data.items){const card=document.createElement('article');
const meta=document.createElement('small');meta.textContent=m.layer+' · '+m.memory_id+' · score '+m.score;
const content=document.createElement('pre');content.textContent=m.content;card.append(meta,content);result.append(card)}
if(!data.items.length)result.textContent='No matching authorized memories.';}catch(e){result.textContent=e.message}}
</script></body></html>"""
