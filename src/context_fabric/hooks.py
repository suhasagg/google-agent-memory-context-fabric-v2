"""Privacy-first, opt-in stdio hooks for supported agent lifecycle events.

Only approved user prompt / summary text is accepted. Tool outputs, commands,
files, environment and raw transcripts are NEVER automatically captured. This
is a limited generic hook adapter, not a native auto-capture plugin for every
coding assistant. Treat agent text as untrusted data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any

from .core import DANGEROUS, Fabric, MemoryInput, Principal

SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\b\s*[:=]|"
    r"\bBearer\s+[A-Za-z0-9_.-]{12,}|"
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|AKIA[A-Z0-9]{16})\b|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def extract_event(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None
    # Specific, opt-in source fields. Never inspect tools, file content or arbitrary JSON.
    content = payload.get("prompt") or payload.get("user_prompt") or payload.get("summary")
    if not isinstance(content,str):
        return None
    content = content.strip()
    if not content or len(content) > 12_000 or DANGEROUS.search(content) or SENSITIVE.search(content):
        return None
    session = payload.get("session_id", "unknown")
    if not isinstance(session,str) or len(session)>128:
        return None
    # Hash user-provided session IDs to avoid raw IDs in long-lived provenance.
    source = hashlib.sha256(session.encode()).hexdigest()[:32]
    return {"content":content,"source_id":source}


def capture_event(payload: Any, *, db: Fabric | None = None) -> dict:
    if os.getenv("FABRIC_AUTO_CAPTURE") != "1":
        return {"stored":False,"reason":"disabled"}
    event=extract_event(payload)
    if not event:
        return {"stored":False,"reason":"filtered"}
    if os.getenv("FABRIC_CAPTURE_DRY_RUN") == "1":
        return {"stored":False,"reason":"dry_run","characters":len(event["content"])}
    principal=Principal(tenant=os.getenv("FABRIC_TENANT","local"),agent=os.getenv("FABRIC_AGENT","hooks"),
                        subject=os.getenv("FABRIC_SUBJECT","local-user"))
    ttl=int(os.getenv("FABRIC_CAPTURE_TTL_DAYS","7"))
    scope={"project":os.getenv("FABRIC_PROJECT","default")}
    owns=db is None
    db=db or Fabric()
    try:
        response=db.write(principal,MemoryInput(content=event["content"],layer="session",
                      source_type="opt_in_agent_hook",source_id=event["source_id"],scope=scope,ttl_days=ttl),
                      idempotency_key=hashlib.sha256((event["source_id"]+event["content"]).encode()).hexdigest())
        return {"stored":True,"memory_id":response["memory_id"],"replayed":response["replayed"]}
    finally:
        if owns:db.close()


def main() -> None:
    if os.getenv("FABRIC_AUTO_CAPTURE") != "1":
        return
    raw=sys.stdin.read(131073)
    if len(raw)>131072:
        return
    try:
        capture_event(json.loads(raw))
    except (ValueError, KeyError, TypeError):
        # Optional hooks must not fail the host agent session.
        return


if __name__=="__main__":main()
