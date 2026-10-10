# Benchmarks: reproducible, not exaggerated

**Data:** `benchmarks/fixtures/coding-agent-mini.json` (12 synthetic snippets / 8 labeled questions), also embedded under the Python package for convenience.

```bash
fabric-evaluate --fixture benchmarks/fixtures/coding-agent-mini.json --mode hybrid --k 3
fabric-evaluate --fixture benchmarks/fixtures/coding-agent-mini.json --mode lexical --k 3
fabric-evaluate --fixture benchmarks/fixtures/coding-agent-mini.json --mode vector --k 3
```

The evaluator starts an isolated temporary database, writes fixtures with stable source IDs, runs policy-filtered searches, and prints per-query ranked IDs. It computes:

- **Recall@K:** fraction of annotated relevant source IDs retrieved in top K per query, averaged across queries.
- **MRR@K:** reciprocal of the first relevant item's rank, averaged over queries.
- **p50/p95 latency:** in-process search times on the running machine only; **not** network round-trip or throughput.
- **Fixture SHA256:** canonical JSON hash to detect accidental corpus changes.

**Observed local smoke run:** hybrid `Recall@3=1.000`, `MRR@3=1.000` on the toy dataset. This is far too small to compare with public long-memory benchmarks; simple lexical overlap makes the fixture relatively easy. Do not interpret this as 100% accuracy on production data.

## Reproduce a fair AgentMemory comparison

1. Obtain authorized benchmark datasets (LongMemEval, LoCoMo or your internal labeled agent sessions) with attribution.
2. Freeze both projects to explicit commit SHAs, record model versions, network access, and CPU/GPU/RAM.
3. Use identical allowed context size, K, metadata access, scopes, relevant annotations and normalization.
4. Run retrieval baselines separately: BM25, learned embeddings, hybrid, graph.
5. Report confidence intervals over queries; measure cold start, P50/P95, throughput, disk cost and capture quality.
6. Include adversarial evaluations: prompt injection, invalid JWTs, grant revocation races, cross-tenant leakage, TTL expiry, backup restoration and PII deletion.
7. Publish reproducible scripts and negative results, not just the best configuration.

Current implementation does **not** supply third-party AgentMemory benchmarks or LongMemEval scores. AgentMemory's public README contains benchmark claims that have not been reproduced for this repository.
