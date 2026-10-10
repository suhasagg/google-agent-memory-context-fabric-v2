"""Offline, reproducible retrieval evaluator. No unsupported benchmark claims.

Dataset schema: [{"query": str, "relevant_source_ids": [str], "scope": optional dict}]
Documents schema: [{"content": str, "source_id": str, "scope": optional dict}]
All content is treated as untrusted data. No network calls by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path

from .core import Fabric, MemoryInput, Principal


def evaluate(documents: list[dict], questions: list[dict], *, k: int = 5, mode: str = "hybrid") -> dict:
    if not 1 <= k <= 100 or mode not in ("lexical", "hybrid", "vector"):
        raise ValueError("invalid k or retrieval mode")
    if not documents or not questions:
        raise ValueError("evaluation inputs cannot be empty")
    ref_to_id: dict[str,str] = {}
    p = Principal(tenant="benchmark",agent="runner")
    with tempfile.TemporaryDirectory() as folder:
        db = Fabric(Path(folder)/"evaluation.sqlite")
        try:
            for doc in documents:
                sid=doc["source_id"]
                if sid in ref_to_id:
                    raise ValueError("duplicate source_id")
                ref_to_id[sid]=db.write(p, MemoryInput(content=doc["content"],source_id=sid,
                                                         scope=doc.get("scope",{}),ttl_days=None))["memory_id"]
            recalls=[]; reciprocal=[]; latencies=[]; detail=[]
            for q in questions:
                relevant={ref_to_id[x] for x in q["relevant_source_ids"]}
                if not relevant:
                    raise ValueError("each query must have at least one relevant document")
                start=time.perf_counter_ns()
                response=db.search(p,q["query"],scope=q.get("scope"),limit=k,
                                   retrieval_mode=mode,token_budget=100000)
                latency=(time.perf_counter_ns()-start)/1e6
                ids=[item["memory_id"] for item in response["items"]]
                hits=len(relevant.intersection(ids))
                recalls.append(hits/len(relevant))
                reciprocal.append(next((1/(idx+1) for idx,mid in enumerate(ids) if mid in relevant),0))
                latencies.append(latency)
                detail.append({"query":q["query"],"hits":hits,"expected":len(relevant),"ranked_source_ids":
                               [documents[next(i for i,d in enumerate(documents) if ref_to_id[d["source_id"]]==mid)]["source_id"] for mid in ids]})
            ordered=sorted(latencies)
            return {"mode":mode,"k":k,"queries":len(questions),"documents":len(documents),
                    "recall_at_k":round(statistics.mean(recalls),4),"mrr_at_k":round(statistics.mean(reciprocal),4),
                    "p50_latency_ms":round(statistics.median(latencies),3),
                    "p95_latency_ms":round(ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))],3),
                    "fixture_sha256":hashlib.sha256(json.dumps({"documents":documents,"questions":questions},sort_keys=True).encode()).hexdigest(),
                    "details":detail}
        finally:
            db.close()


def main(argv=None):
    ap=argparse.ArgumentParser(description="Evaluate local retrieval; no AgentMemory comparison implied")
    ap.add_argument("--fixture",default=str(Path(__file__).resolve().parent/"fixtures"/"coding-agent-mini.json"))
    ap.add_argument("--mode",choices=("hybrid","lexical","vector"),default="hybrid")
    ap.add_argument("--k",type=int,default=5)
    ns=ap.parse_args(argv)
    data=json.loads(Path(ns.fixture).read_text())
    print(json.dumps(evaluate(data["documents"],data["questions"],k=ns.k,mode=ns.mode),indent=2))


if __name__=="__main__":main()
