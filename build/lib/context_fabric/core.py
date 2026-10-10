"""Authoritative SQLite memory store. No hosted service, model key or external DB required.

Invariant: retrieved memory is untrusted data, never tool authority. All reads/writes
are tenant and agent scoped. This local runtime is single-process/small-team; do not
mistake its static-key auth for production OIDC or distributed consistency.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import tempfile
import shutil
import os
import re
import secrets
import sqlite3
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LAYERS = ("working", "session", "episodic", "semantic", "entity", "procedural")
CLASSIFICATION = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}
TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)
DANGEROUS = re.compile(r"(?i)(ignore (all |previous )?instructions|reveal (your |the )?(system|secret)|disable (your )?safety|exfiltrat|send (the )?api.key)")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokens(s: str) -> list[str]:
    return TOKEN_RE.findall(s.lower())


def vector(s: str, dim: int = 256) -> list[float]:
    out = [0.0] * dim
    for word in tokens(s):
        digest = hashlib.sha256(word.encode()).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1 if digest[4] & 1 else -1
        out[idx] += sign
    length = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / length for x in out]


def similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def matching_scope(actual: dict, expected: dict) -> bool:
    return all(actual.get(k) == v for k, v in expected.items())


@dataclass(frozen=True)
class Principal:
    tenant: str = "local"
    agent: str = "cli"
    subject: str = "local-user"
    clearance: str = "INTERNAL"
    roles: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.tenant or not self.agent or not self.subject or self.clearance not in CLASSIFICATION:
            raise ValueError("invalid principal")

    def can(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


@dataclass
class MemoryInput:
    content: str
    layer: str = "semantic"
    scope: dict[str, str] = field(default_factory=dict)
    classification: str = "INTERNAL"
    confidence: float = 1.0
    source_type: str = "manual"
    source_id: str = "user"
    evidence: dict[str, Any] = field(default_factory=dict)
    ttl_days: int | None = 90
    purpose: str = "context"
    verified: bool = False
    valid_from: str | None = None
    valid_to: str | None = None

    def validate(self):
        if not self.content.strip() or len(self.content) > 100_000:
            raise ValueError("content must be 1..100000 characters")
        if self.layer not in LAYERS or self.classification not in CLASSIFICATION:
            raise ValueError("invalid layer or classification")
        if isinstance(self.confidence,bool) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be 0..1")
        if not self.source_id or not self.source_type:
            raise ValueError("source_type and source_id are required")
        for key in ("valid_from","valid_to"):
            value=getattr(self,key)
            if value is not None:
                try:
                    parsed=datetime.fromisoformat(value)
                except (ValueError,TypeError):
                    raise ValueError(f"{key} must be ISO 8601 datetime") from None
                if parsed.tzinfo is None:
                    raise ValueError(f"{key} must include timezone")
                setattr(self,key,parsed.astimezone(timezone.utc).isoformat())
        if self.valid_from and self.valid_to and self.valid_from>=self.valid_to:
            raise ValueError("valid_from must precede valid_to")
        if self.ttl_days is not None and not 0 <= self.ttl_days <= 36500:
            raise ValueError("ttl_days must be 0..36500 or null")
        if not self.purpose.strip():
            raise ValueError("purpose is required")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.scope.items()):
            raise ValueError("scope keys and values must be strings")


class Forbidden(PermissionError):
    pass


class Missing(LookupError):
    pass


class Conflict(RuntimeError):
    pass


class Fabric:
    def __init__(self, path: str | Path | None = None):
        self.path = str(Path(path or os.environ.get("FABRIC_DB", str(Path.home() / ".context-fabric" / "memory.db"))).expanduser()) if path != ":memory:" else ":memory:"
        if self.path != ":memory:":
            directory = Path(self.path).parent
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Create DB with private permissions before sqlite opens it.
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
            if os.getenv("FABRIC_MODE") == "production" and Path(self.path).stat().st_mode & 0o077:
                raise PermissionError("production SQLite DB must be mode 0600 or more restrictive")
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=15)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA trusted_schema=OFF")
        self._db.execute("PRAGMA secure_delete=ON")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA busy_timeout=15000")
        if self.path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.RLock()
        self._embedding_cache: dict[tuple[str, int, str, str], list[float]] = {}
        self._init_schema()

    def close(self):
        self._db.close()

    def verify_integrity(self) -> dict:
        """Read-only SQLite integrity diagnostic and tracked table counts."""
        with self._lock:
            integrity = [r[0] for r in self._db.execute("PRAGMA integrity_check")]
            counts = {table: self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("memories", "revisions", "grants", "edges", "audit", "outbox")}
            return {"ok": integrity == ["ok"], "checks": integrity, "counts": counts}

    def backup(self, destination: str | Path) -> dict:
        """Consistent, online SQLite backup; never overwrite existing files."""
        if self.path == ":memory:":
            raise ValueError("persistent database required for backup")
        target = Path(destination).expanduser().absolute()
        if target == Path(self.path).absolute() or target.exists():
            raise FileExistsError("backup destination must be a new file distinct from the live DB")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._lock:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
            try:
                with sqlite3.connect(str(target)) as dst:
                    self._db.backup(dst)
                with sqlite3.connect(str(target)) as check:
                    result = check.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise RuntimeError("backup integrity check failed")
            except Exception:
                target.unlink(missing_ok=True)
                raise
        return {"backup": str(target), "bytes": target.stat().st_size, "integrity": "ok"}

    def checkpoint(self) -> dict:
        """Checkpoint WAL and shrink it when no conflicting readers exist."""
        if self.path == ":memory:":
            return {"checkpoint": "in-memory"}
        with self._lock:
            busy, frames, done = self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        return {"busy": bool(busy), "frames": frames, "checkpointed": done}

    def _search_candidates(self, p: Principal, purpose: str, scope: dict | None,
                           layers: list[str] | None, candidate_limit: int) -> list[dict]:
        # A filtered, bounded query, not list_memories()'s 500-result page.
        with self._lock:
            query = ("SELECT * FROM memories WHERE tenant=? AND status='ACTIVE' "
                     "AND (expires_at IS NULL OR expires_at > ?) "
                     "AND (valid_from IS NULL OR valid_from <= ?) "
                     "AND (valid_to IS NULL OR valid_to > ?)")
            args = [p.tenant, now(), now(), now()]
            if layers:
                query += " AND layer IN (" + ",".join("?" for _ in layers) + ")"
                args.extend(layers)
            if not p.can("all_purposes"):
                query += " AND purpose=?"
                args.append(purpose)
            if scope:
                if len(scope) > 20:
                    raise ValueError("scope supports at most 20 keys")
                for k, v in scope.items():
                    if not isinstance(k, str) or not isinstance(v, str):
                        raise ValueError("scope keys and values must be strings")
                    query += " AND json_extract(scope, ?) = ?"
                    args.extend(["$." + json.dumps(k), v])
            query += " ORDER BY created_at DESC LIMIT ?"
            args.append(candidate_limit + 1)
            rows = self._db.execute(query, args).fetchall()
            if len(rows) > candidate_limit:
                raise ValueError("too many candidate memories; narrow search scope or deploy indexed retrieval")
            return [m for r in rows if (m := self._row(r)) and self._base_access(p,m,purpose,scope)
                    and (not layers or m["layer"] in layers)]

    def _init_schema(self):
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, owner TEXT NOT NULL,
            layer TEXT NOT NULL, scope TEXT NOT NULL, content TEXT NOT NULL,
            classification TEXT NOT NULL, confidence REAL NOT NULL,
            purpose TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
            evidence TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ACTIVE', version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            expires_at TEXT, valid_from TEXT, valid_to TEXT,
            legal_hold INTEGER NOT NULL DEFAULT 0, content_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_visibility ON memories(tenant,owner,status,layer);
        CREATE TABLE IF NOT EXISTS revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL,
            version INTEGER NOT NULL, content TEXT NOT NULL, actor TEXT NOT NULL,
            source_type TEXT NOT NULL, source_id TEXT NOT NULL, evidence TEXT NOT NULL,
            reason TEXT NOT NULL, at TEXT NOT NULL, FOREIGN KEY(memory_id) REFERENCES memories(id)
        );
        CREATE TABLE IF NOT EXISTS grants (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL, layers TEXT NOT NULL, scope TEXT NOT NULL,
            purposes TEXT NOT NULL, expires_at TEXT, revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS edges (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, from_id TEXT NOT NULL,
            to_id TEXT NOT NULL, relation TEXT NOT NULL, actor TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(tenant,from_id,to_id,relation),
            FOREIGN KEY(from_id) REFERENCES memories(id), FOREIGN KEY(to_id) REFERENCES memories(id)
        );
        CREATE TABLE IF NOT EXISTS profiles (
            tenant TEXT NOT NULL, agent TEXT NOT NULL, name TEXT NOT NULL,
            fields TEXT NOT NULL, schema TEXT NOT NULL, version INTEGER NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(tenant,agent,name)
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, actor TEXT NOT NULL,
            action TEXT NOT NULL, object_id TEXT, details TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS outbox (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, event_type TEXT NOT NULL,
            object_id TEXT NOT NULL, payload TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS idempotency (
            tenant TEXT NOT NULL, agent TEXT NOT NULL, key TEXT NOT NULL,
            request_hash TEXT NOT NULL, memory_id TEXT NOT NULL,
            PRIMARY KEY(tenant,agent,key)
        );
        """)
        # Backward-compatible additive migration. Existing audit events cannot
        # become tamper-evident retroactively and remain explicitly unsealed.
        columns = {r[1] for r in self._db.execute("PRAGMA table_info(audit)")}
        for name in ("prev_mac", "entry_mac"):
            if name not in columns:
                self._db.execute(f"ALTER TABLE audit ADD COLUMN {name} TEXT")

    @staticmethod
    def _audit_payload(tenant: str, actor: str, action: str, obj: str | None,
                       details: str, stamp: str, prev: str) -> bytes:
        return json.dumps({"tenant":tenant,"actor":actor,"action":action,
                           "object_id":obj,"details":details,"created_at":stamp,
                           "prev_mac":prev}, sort_keys=True,separators=(",", ":")).encode()

    def _audit(self, p: Principal, action: str, obj: str | None = None, details: dict | None = None):
        stamp=now()
        encoded=json.dumps(details or {},sort_keys=True,separators=(",", ":"))
        key=os.getenv("FABRIC_AUDIT_HMAC_KEY")
        if key:
            if len(key.encode()) < 32:
                raise ValueError("FABRIC_AUDIT_HMAC_KEY must be at least 32 bytes")
            previous=self._db.execute("SELECT entry_mac FROM audit WHERE tenant=? ORDER BY id DESC LIMIT 1",(p.tenant,)).fetchone()
            prev=(previous["entry_mac"] or "") if previous else ""
            mac=hmac.new(key.encode(),self._audit_payload(p.tenant,p.agent,action,obj,encoded,stamp,prev),hashlib.sha256).hexdigest()
            self._db.execute("INSERT INTO audit(tenant,actor,action,object_id,details,created_at,prev_mac,entry_mac) VALUES (?,?,?,?,?,?,?,?)",
                             (p.tenant,p.agent,action,obj,encoded,stamp,prev,mac))
        else:
            self._db.execute("INSERT INTO audit(tenant,actor,action,object_id,details,created_at) VALUES (?,?,?,?,?,?)",
                             (p.tenant,p.agent,action,obj,encoded,stamp))

    def verify_audit_chain(self,p:Principal) -> dict:
        if not p.can("admin"):
            raise Forbidden("admin role required")
        key=os.getenv("FABRIC_AUDIT_HMAC_KEY")
        if not key:
            return {"valid":False,"status":"audit HMAC not configured"}
        prev="";count=0
        with self._lock:
            for record in self._db.execute("SELECT * FROM audit WHERE tenant=? ORDER BY id",(p.tenant,)):
                if not record["entry_mac"]:
                    return {"valid":False,"status":"legacy/unsealed audit rows", "verified_events":count}
                payload=self._audit_payload(record["tenant"],record["actor"],record["action"],
                                            record["object_id"],record["details"],record["created_at"],prev)
                expected=hmac.new(key.encode(),payload,hashlib.sha256).hexdigest()
                if record["prev_mac"]!=prev or not hmac.compare_digest(record["entry_mac"],expected):
                    return {"valid":False,"status":"audit integrity mismatch", "verified_events":count}
                prev=record["entry_mac"]
                count+=1
        return {"valid":True,"status":"ok","verified_events":count,"head_mac":prev}

    def _event(self, p: Principal, event: str, obj: str, payload: dict | None = None):
        self._db.execute("INSERT INTO outbox VALUES (?,?,?,?,?,?,?)",
                         (str(uuid.uuid4()), p.tenant, event, obj, json.dumps(payload or {}), 0, now()))

    def _transaction(self, operation):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                result = operation()
                self._db.execute("COMMIT")
                return result
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def _row(self, row) -> dict:
        d = dict(row)
        for k in ("scope", "evidence"):
            d[k] = json.loads(d[k])
        for k in ("verified", "legal_hold"):
            d[k] = bool(d[k])
        return d

    def _base_access(self, p: Principal, m: dict, purpose: str, scope: dict | None = None) -> bool:
        if m["tenant"] != p.tenant or m["status"] != "ACTIVE":
            return False
        if m["expires_at"] and m["expires_at"] <= now():
            return False
        if m["valid_from"] and m["valid_from"] > now():
            return False
        if m["valid_to"] and m["valid_to"] <= now():
            return False
        if CLASSIFICATION[m["classification"]] > CLASSIFICATION[p.clearance]:
            return False
        if m["purpose"] != purpose and not p.can("all_purposes"):
            return False
        if scope and not matching_scope(m["scope"], scope):
            return False
        if m["owner"] == p.agent or p.can("tenant_reader"):
            return True
        if m["layer"] == "working":
            return False
        for r in self._db.execute("SELECT * FROM grants WHERE tenant=? AND from_agent=? AND to_agent=? AND revoked=0",
                                  (p.tenant, m["owner"], p.agent)):
            if r["expires_at"] and r["expires_at"] <= now():
                continue
            if m["layer"] in json.loads(r["layers"]) and purpose in json.loads(r["purposes"]) and matching_scope(m["scope"], json.loads(r["scope"])):
                return True
        return False

    def write(self, p: Principal, memory: MemoryInput, idempotency_key: str | None = None) -> dict:
        memory.validate()
        if idempotency_key is not None and (not 1 <= len(idempotency_key) <= 128 or not idempotency_key.isascii()):
            raise ValueError("idempotency key must contain 1..128 ASCII characters")
        if memory.classification == "CONFIDENTIAL" and CLASSIFICATION[p.clearance] < 2 or memory.classification == "RESTRICTED" and CLASSIFICATION[p.clearance] < 3:
            raise Forbidden("writer lacks classification clearance")
        if memory.layer == "procedural" and (not memory.verified or not p.can("procedure_approver")):
            raise Forbidden("procedural memory requires verified=True and procedure_approver role")
        if any(k in {"tenant", "tenant_id", "agent_id", "owner"} for k in memory.scope):
            raise ValueError("reserved scope key")
        if DANGEROUS.search(memory.content) and memory.layer == "procedural":
            raise Forbidden("suspected instruction injection in procedural memory")
        mid = str(uuid.uuid4())
        stamp = now()
        expires = (datetime.now(timezone.utc) + timedelta(days=memory.ttl_days)).isoformat() if memory.ttl_days is not None else None
        content_hash = hashlib.sha256(memory.content.encode()).hexdigest()
        request_hash = hashlib.sha256(json.dumps(memory.__dict__, sort_keys=True).encode()).hexdigest()

        def perform():
            if idempotency_key:
                old = self._db.execute("SELECT request_hash,memory_id FROM idempotency WHERE tenant=? AND agent=? AND key=?", (p.tenant,p.agent,idempotency_key)).fetchone()
                if old:
                    if old["request_hash"] != request_hash:
                        raise Conflict("idempotency key reused with different payload")
                    return {"memory_id": old["memory_id"], "replayed": True}
            self._db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid,p.tenant,p.agent,memory.layer,json.dumps(memory.scope),memory.content,memory.classification,
                 memory.confidence,memory.purpose,memory.source_type,memory.source_id,json.dumps(memory.evidence),
                 int(memory.verified),"ACTIVE",1,stamp,stamp,expires,memory.valid_from,memory.valid_to,0,content_hash))
            self._db.execute("INSERT INTO revisions(memory_id,version,content,actor,source_type,source_id,evidence,reason,at) VALUES (?,?,?,?,?,?,?,?,?)",
                             (mid,1,memory.content,p.agent,memory.source_type,memory.source_id,json.dumps(memory.evidence),"created",stamp))
            if idempotency_key:
                self._db.execute("INSERT INTO idempotency VALUES (?,?,?,?,?)", (p.tenant,p.agent,idempotency_key,request_hash,mid))
            self._audit(p,"memory.created",mid,{"layer":memory.layer, "classification":memory.classification})
            self._event(p,"memory.created",mid,{"version":1})
            return {"memory_id":mid,"version":1,"replayed":False}
        return self._transaction(perform)

    def get(self, p: Principal, memory_id: str, purpose: str = "context") -> dict:
        with self._lock:
            row = self._db.execute("SELECT * FROM memories WHERE id=? AND tenant=?", (memory_id,p.tenant)).fetchone()
            if not row or not self._base_access(p,self._row(row),purpose):
                raise Missing("memory not found")
            record=self._row(row)
            if CLASSIFICATION[record["classification"]]>=2:
                self._audit(p,"memory.sensitive_read",memory_id,{"purpose":purpose})
            return record

    def list_memories(self, p: Principal, scope: dict | None = None, layer: str | None = None,
                      purpose: str = "context", limit: int = 100, offset: int = 0) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM memories WHERE tenant=? AND status='ACTIVE' ORDER BY created_at DESC",
                                    (p.tenant,)).fetchall()
            permitted = [self._row(r) for r in rows]
            permitted = [m for m in permitted if self._base_access(p,m,purpose,scope) and (layer is None or layer==m["layer"])]
            return permitted[max(offset,0):max(offset,0)+max(0,min(limit,500))]

    def update(self, p: Principal, memory_id: str, content: str, expected_version: int, reason: str = "revision",
               source_id: str = "manual") -> dict:
        if not content.strip() or len(content) > 100_000:
            raise ValueError("invalid content length")
        def perform():
            m = self.get(p,memory_id)
            if m["owner"] != p.agent and not p.can("admin"):
                raise Forbidden("only memory owner can revise")
            if m["version"] != expected_version:
                raise Conflict("version mismatch")
            if m["layer"] == "procedural" and not p.can("procedure_approver"):
                raise Forbidden("procedure approval role required")
            newv=m["version"]+1
            self._db.execute("UPDATE memories SET content=?,content_hash=?,version=?,updated_at=? WHERE id=?",
                             (content,hashlib.sha256(content.encode()).hexdigest(),newv,now(),memory_id))
            self._db.execute("INSERT INTO revisions(memory_id,version,content,actor,source_type,source_id,evidence,reason,at) VALUES (?,?,?,?,?,?,?,?,?)",
                             (memory_id,newv,content,p.agent,"manual",source_id,"{}",reason,now()))
            self._embedding_cache.clear()
            self._audit(p,"memory.revised",memory_id,{"version":newv})
            self._event(p,"memory.updated",memory_id,{"version":newv})
            return {"memory_id":memory_id,"version":newv}
        return self._transaction(perform)

    def history(self, p: Principal, memory_id: str) -> list[dict]:
        m = self.get(p,memory_id)
        if m["owner"] != p.agent and not p.can("admin"):
            raise Forbidden("revisions require ownership")
        with self._lock:
            return [dict(r) for r in self._db.execute("SELECT * FROM revisions WHERE memory_id=? ORDER BY version",(memory_id,))]

    def forget(self, p: Principal, memory_id: str, reason: str = "user request") -> dict:
        def perform():
            raw = self._db.execute("SELECT * FROM memories WHERE id=? AND tenant=?",(memory_id,p.tenant)).fetchone()
            if not raw or raw["status"] != "ACTIVE":
                raise Missing("memory not found")
            m = self._row(raw)
            if m["owner"] != p.agent and not p.can("admin"):
                raise Forbidden("only memory owner can forget")
            if m["legal_hold"]:
                raise Conflict("memory under legal hold")
            self._db.execute("UPDATE memories SET status='FORGOTTEN', content='', evidence='{}', content_hash='', updated_at=? WHERE id=?", (now(),memory_id))
            self._db.execute("UPDATE revisions SET content='', evidence='{}' WHERE memory_id=?", (memory_id,))
            self._db.execute("DELETE FROM edges WHERE from_id=? OR to_id=?", (memory_id,memory_id))
            self._db.execute("DELETE FROM idempotency WHERE memory_id=?", (memory_id,))
            self._embedding_cache.clear()
            self._audit(p,"memory.forgotten",memory_id,{"reason":reason})
            self._event(p,"memory.forgotten",memory_id,{})
            return {"memory_id":memory_id,"status":"FORGOTTEN"}
        return self._transaction(perform)

    def set_hold(self, p: Principal, memory_id: str, enabled: bool) -> dict:
        if not p.can("admin"):
            raise Forbidden("admin role required")
        def perform():
            m=self.get(p,memory_id)
            self._db.execute("UPDATE memories SET legal_hold=? WHERE id=?",(int(enabled),memory_id))
            self._audit(p,"memory.legal_hold",memory_id,{"enabled":enabled})
            return {"memory_id":memory_id,"legal_hold":enabled}
        return self._transaction(perform)

    def grant(self, p: Principal, to_agent: str, layers: list[str], scope: dict | None = None,
              purposes: list[str] | None = None, ttl_days: int = 7) -> dict:
        if not to_agent or to_agent == p.agent or not layers or any(l not in LAYERS or l == "working" for l in layers):
            raise ValueError("invalid destination or shareable layers")
        if not 0 < ttl_days <= 365:
            raise ValueError("grant ttl_days must be 1..365")
        if any(k in {"tenant", "tenant_id", "agent_id", "owner"} for k in (scope or {})):
            raise ValueError("reserved scope key")
        gid=str(uuid.uuid4())
        expires=(datetime.now(timezone.utc)+timedelta(days=ttl_days)).isoformat()
        def perform():
            self._db.execute("INSERT INTO grants VALUES (?,?,?,?,?,?,?,?,?,?)",(gid,p.tenant,p.agent,to_agent,json.dumps(layers),json.dumps(scope or {}),json.dumps(purposes or ["context"]),expires,0,now()))
            self._audit(p,"grant.created",gid,{"to_agent":to_agent})
            self._event(p,"grant.created",gid,{})
            return {"grant_id":gid,"expires_at":expires}
        return self._transaction(perform)

    def revoke(self, p: Principal, grant_id: str) -> dict:
        def perform():
            g=self._db.execute("SELECT * FROM grants WHERE id=? AND tenant=?",(grant_id,p.tenant)).fetchone()
            if not g or (g["from_agent"] != p.agent and not p.can("admin")):
                raise Missing("grant not found")
            self._db.execute("UPDATE grants SET revoked=1 WHERE id=?",(grant_id,))
            self._audit(p,"grant.revoked",grant_id)
            self._event(p,"grant.revoked",grant_id,{})
            return {"grant_id":grant_id,"revoked":True}
        return self._transaction(perform)

    def link(self, p: Principal, from_id: str, to_id: str, relation: str = "related_to") -> dict:
        if not relation or len(relation) > 64 or not re.fullmatch(r"[a-zA-Z0-9_:-]+",relation):
            raise ValueError("invalid relation")
        if from_id == to_id:
            raise ValueError("self-loop not allowed")
        self.get(p,from_id); self.get(p,to_id)
        eid=str(uuid.uuid4())
        def perform():
            self._db.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?,?,?)",(eid,p.tenant,from_id,to_id,relation,p.agent,now()))
            r=self._db.execute("SELECT id FROM edges WHERE tenant=? AND from_id=? AND to_id=? AND relation=?",(p.tenant,from_id,to_id,relation)).fetchone()
            self._audit(p,"edge.linked",r["id"])
            self._event(p,"edge.linked",r["id"],{})
            return {"edge_id":r["id"]}
        return self._transaction(perform)

    def neighbors(self,p:Principal,memory_id:str,purpose:str="context",depth:int=1,limit:int=50)->list[dict]:
        self.get(p,memory_id,purpose)
        visited={memory_id};front={memory_id};found=[]
        with self._lock:
            for _ in range(max(0,min(depth,3))):
                nxt=set()
                for src in front:
                    for r in self._db.execute("SELECT * FROM edges WHERE tenant=? AND (from_id=? OR to_id=?)",(p.tenant,src,src)):
                        nid=r["to_id"] if r["from_id"]==src else r["from_id"]
                        if nid in visited: continue
                        try:
                            m=self.get(p,nid,purpose)
                        except Missing:
                            continue
                        nxt.add(nid);found.append({"memory":m,"relation":r["relation"]})
                        if len(found)>=limit: return found
                visited.update(nxt);front=nxt
                if not front: break
        return found

    def profile_set(self,p:Principal,name:str,fields:dict,schema:dict,expected_version:int|None=None)->dict:
        if not name or len(name)>100 or not isinstance(fields,dict) or not isinstance(schema,dict):
            raise ValueError("invalid profile")
        # Simple explicitly declared field types; reject unknown keys, never execute schema.
        for k,v in fields.items():
            if k not in schema or schema[k] not in ("str","int","float","bool","list","dict"):
                raise ValueError(f"undeclared or invalid schema field: {k}")
            types={"str":str,"int":int,"float":(float,int),"bool":bool,"list":list,"dict":dict}
            if not isinstance(v,types[schema[k]]) or (schema[k] in ("int", "float") and isinstance(v,bool)):
                raise ValueError(f"field {k} fails schema type {schema[k]}")
        def perform():
            old=self._db.execute("SELECT * FROM profiles WHERE tenant=? AND agent=? AND name=?",(p.tenant,p.agent,name)).fetchone()
            if old and expected_version != old["version"]:
                raise Conflict("profile version mismatch")
            if not old and expected_version not in (None,0):
                raise Conflict("profile does not exist")
            version=old["version"]+1 if old else 1
            self._db.execute("INSERT INTO profiles VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant,agent,name) DO UPDATE SET fields=excluded.fields,schema=excluded.schema,version=excluded.version,updated_at=excluded.updated_at",(p.tenant,p.agent,name,json.dumps(fields),json.dumps(schema),version,now()))
            self._audit(p,"profile.updated",name,{"version":version})
            self._event(p,"profile.updated",name,{"version":version})
            return {"name":name,"version":version}
        return self._transaction(perform)

    def profile_get(self,p:Principal,name:str)->dict:
        row=self._db.execute("SELECT * FROM profiles WHERE tenant=? AND agent=? AND name=?",(p.tenant,p.agent,name)).fetchone()
        if not row:raise Missing("profile not found")
        return {"name":name,"fields":json.loads(row["fields"]),"schema":json.loads(row["schema"]),"version":row["version"],"updated_at":row["updated_at"]}

    def conflicts(self,p:Principal,content:str,scope:dict|None=None,threshold:float=.40)->list[dict]:
        q=vector(content)
        ranked=[{"memory_id":m["id"],"similarity":round(similarity(q,vector(m["content"])),4),"existing":m["content"]}
                for m in self.list_memories(p,scope=scope,limit=500)]
        return sorted((x for x in ranked if x["similarity"]>=threshold),key=lambda x:-x["similarity"])

    def search(self,p:Principal,query:str,scope:dict|None=None,layers:list[str]|None=None,
               purpose:str="context",limit:int=10,token_budget:int=2000,graph_depth:int=0,
               retrieval_mode:str="hybrid")->dict:
        if not 0 < limit <= 100 or not 0 < token_budget <= 100000:
            raise ValueError("limit must be 1..100 and token_budget 1..100000")
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise ValueError("query must contain 1..4000 characters")
        if graph_depth not in (0, 1, 2, 3):
            raise ValueError("graph_depth must be 0..3")
        if retrieval_mode not in ("hybrid", "lexical", "vector"):
            raise ValueError("retrieval_mode must be hybrid, lexical or vector")
        if layers and any(l not in LAYERS for l in layers):
            raise ValueError("invalid layer")
        # Authorization before scoring: candidate set includes only permitted memories.
        max_candidates = int(os.getenv("FABRIC_SEARCH_MAX_CANDIDATES", "5000"))
        if not 100 <= max_candidates <= 100_000:
            raise ValueError("FABRIC_SEARCH_MAX_CANDIDATES must be 100..100000")
        docs=self._search_candidates(p,purpose,scope,layers,max_candidates)
        qwords=tokens(query)
        counts=[Counter(tokens(m["content"])) for m in docs]
        df=Counter(word for c in counts for word in c)
        n=len(docs); avgdl=(sum(sum(c.values()) for c in counts)/n) if n else 1
        bm=[]; vec=[]
        from .embeddings import embed
        backend=os.environ.get("FABRIC_EMBEDDING_BACKEND","hash")
        model=os.environ.get("FABRIC_EMBEDDING_MODEL","")
        qv=embed(query)
        for i,(m,c) in enumerate(zip(docs,counts)):
            dl=sum(c.values());lex=0.0
            for term in set(qwords):
                f=c[term]
                if f:
                    idf=math.log(1+(n-df[term]+.5)/(df[term]+.5))
                    lex+=idf*f*2.2/(f+1.2*(.25+.75*dl/(avgdl or 1)))
            bm.append((lex,i))
            cache_key=(m["id"],m["version"],backend,model)
            if cache_key not in self._embedding_cache:
                self._embedding_cache[cache_key]=embed(m["content"])
            vec.append((similarity(qv,self._embedding_cache[cache_key]),i))
        bm.sort(key=lambda x:(-x[0],docs[x[1]]["id"]))
        vec.sort(key=lambda x:(-x[0],docs[x[1]]["id"]))
        scores=defaultdict(float)
        if retrieval_mode in ("hybrid", "lexical"):
            for rank,(score,idx) in enumerate(bm):
                if score>0:scores[idx]+=1/(60+rank+1)
        if retrieval_mode in ("hybrid", "vector"):
            for rank,(score,idx) in enumerate(vec):
                if score>0:scores[idx]+=1/(60+rank+1)
        # Scope & authorizations above; graph expansion never grants wider access.
        if graph_depth:
            seeds=[docs[idx]["id"] for _,idx in bm[:min(3,len(bm))] if _>0]
            ids={m["id"]:i for i,m in enumerate(docs)}
            for seed in seeds:
                for m in self.neighbors(p,seed,purpose,depth=graph_depth,limit=50):
                    idx=ids.get(m["memory"]["id"])
                    if idx is not None:scores[idx]+=.004
        for idx in scores:
            scores[idx] *= (.5 + .5 * docs[idx]["confidence"])
        ordered=sorted(scores,key=lambda i:(-scores[i],docs[i]["id"]))
        items=[];budget=token_budget
        for idx in ordered:
            m=docs[idx]
            cost=max(1,len(tokens(m["content"])))
            if cost>budget:continue
            budget-=cost
            items.append({"memory_id":m["id"],"content":m["content"],"layer":m["layer"],"score":round(scores[idx],6),
                          "classification":m["classification"],"scope":m["scope"],"confidence":m["confidence"],
                          "provenance":{"source_type":m["source_type"],"source_id":m["source_id"],"evidence":m["evidence"],"version":m["version"]},
                          "untrusted":True,"possible_instruction_injection":bool(DANGEROUS.search(m["content"]))})
            if len(items)>=limit:break
        with self._lock:
            self._audit(p,"memory.searched",None,{"query_hash":hashlib.sha256(query.encode()).hexdigest(),"returned":len(items),"purpose":purpose})
        return {"query":query,"items":items,"token_budget_used":token_budget-budget,
                "authorization_note":"Memory is untrusted context only, never identity, approval or permission.",
                "retrieval":retrieval_mode,
                "embedding_backend":backend,
                "candidate_count":len(docs)}

    def consolidate_candidates(self,p:Principal,threshold:float=.85,limit:int=50)->list[dict]:
        """Detect candidate duplicates; never merge silently or discard provenance."""
        mem=self.list_memories(p,limit=500)
        result=[]
        for i,m in enumerate(mem):
            for other in mem[i+1:]:
                if m["layer"]!=other["layer"] or m["scope"]!=other["scope"]:continue
                score=similarity(vector(m["content"]),vector(other["content"]))
                if score>=threshold:
                    result.append({"ids":[m["id"],other["id"]],"similarity":round(score,4),"review_required":True})
                    if len(result)>=limit:return result
        return result

    def sweep_expired(self,p:Principal)->dict:
        if not p.can("admin"):
            raise Forbidden("admin role required")
        with self._lock:
            ids=[r["id"] for r in self._db.execute("SELECT id FROM memories WHERE tenant=? AND status='ACTIVE' AND legal_hold=0 AND expires_at <= ?",(p.tenant,now()))]
        count=0
        for mid in ids:
            try:self.forget(p,mid,"ttl expired");count+=1
            except (Missing,Conflict):pass
        return {"expired":count}

    def audit_events(self,p:Principal,limit:int=100)->list[dict]:
        if not p.can("admin"):
            raise Forbidden("admin role required")
        return [dict(r) for r in self._db.execute("SELECT * FROM audit WHERE tenant=? ORDER BY id DESC LIMIT ?",(p.tenant,min(limit,500)))]

    def outbox_events(self,p:Principal,limit:int=100)->list[dict]:
        if not p.can("admin"):
            raise Forbidden("admin role required")
        return [dict(r) for r in self._db.execute("SELECT * FROM outbox WHERE tenant=? ORDER BY created_at DESC LIMIT ?",(p.tenant,min(limit,500)))]

    def drain_outbox(self,p:Principal,handler,limit:int=100)->dict:
        """At-least-once local dispatcher. Handler must be idempotent. Retry failed events."""
        if not p.can("admin"):
            raise Forbidden("admin role required")
        events=self._db.execute("SELECT * FROM outbox WHERE tenant=? AND published=0 ORDER BY created_at LIMIT ?",(p.tenant,limit)).fetchall()
        handled=0
        for evt in events:
            handler(dict(evt))
            with self._lock:
                self._db.execute("UPDATE outbox SET published=1 WHERE id=? AND tenant=?",(evt["id"],p.tenant))
            handled+=1
        return {"published":handled}
