"""Tiny reproducible smoke benchmark, not a third-party competitive evaluation."""
from __future__ import annotations
import statistics
import time
from .core import Fabric, Principal, MemoryInput

CORPUS=[
    ("auth","The authentication stack relies on jose JWT middleware in src/auth.py"),
    ("db","Database migrations use Alembic and PostgreSQL"),
    ("cache","The cache uses Redis with per-key expiration"),
    ("tests","Unit tests run with pytest and GitHub Actions"),
    ("agent","The agent orchestrator uses a durable checkpoint store"),
    ("search","Retrieval combines BM25 lexical scoring and vector similarity"),
    ("logging","Observability traces flow through OpenTelemetry"),
    ("docs","Architecture decisions are recorded in ADR markdown files"),
]
QUERIES=[("JWT middleware","auth"),("Alembic migrations","db"),("Redis expiration","cache"),
         ("pytest CI","tests"),("BM25 retrieval","search"),("OpenTelemetry traces","logging")]


def run():
    db=Fabric(":memory:");p=Principal()
    ids={}
    for key, content in CORPUS:
        ids[key]=db.write(p,MemoryInput(content=content,source_id="benchmark"))["memory_id"]
    latencies=[];hits=0;top5=0
    for query,expected in QUERIES:
        start=time.perf_counter()
        items=db.search(p,query,limit=5)["items"]
        latencies.append((time.perf_counter()-start)*1000)
        hits+=bool(items and items[0]["memory_id"]==ids[expected])
        top5+=any(i["memory_id"]==ids[expected] for i in items)
    result={"corpus_size":len(CORPUS),"queries":len(QUERIES),"top1_accuracy":round(hits/len(QUERIES),3),
            "recall_at_5":round(top5/len(QUERIES),3),"latency_p50_ms":round(statistics.median(latencies),3),
            "caveat":"Small synthetic exact-term benchmark; not comparable to published AgentMemory benchmarks."}
    db.close();return result


if __name__ == "__main__":
    import json
    print(json.dumps(run(),indent=2))
