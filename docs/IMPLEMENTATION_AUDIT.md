# Implementation audit — v3.0.0-rc1

**Audit basis:** Source inspection + 47 automated Python tests and synthetic retrieval run on 2026-10-09. This is not an independent security audit or a production certification.

| Capability | Implementation | What has been verified | Important limit |
|---|---|---|---|
| Six memory layers | `src/context_fabric/core.py` | Write/read and layer checks | Writer assigns layer |
| Transactional persistence | `core.Fabric` SQLite WAL | Revisions, atomic writes, idempotency | Single-node deployment |
| Isolation | `core._base_access` | Tenant, owner, grants, classification, scope, purpose | Local CLI identities are trusted process args |
| Sharing/revocation | `grant`, `revoke` | Tests for restricted access | No enterprise admin console |
| Temporal data | `valid_from`, `valid_to`, TTL | Tested validation and sweep | Scheduler is external, must invoke sweep |
| Legal hold | `set_hold`, `forget` | Hold forbids forget | No litigation discovery system |
| Knowledge graph | `edges`, `neighbors` | ACL checked traversal | No Neo4j backend |
| Hybrid retrieval | `search` | BM25, vector, RRF, optional graph | Scan, <= configured filtered candidate cap |
| Learned embeddings | `embeddings.py` | Code path present | Model dependency not exercised here |
| FastAPI REST | `api.py` | Authenticated create/search/forget, metrics, privacy headers | Reverse proxy mandatory for public access |
| OIDC/JWKS | `security.py` | Offline test checks actual RSA signatures and claims | Real IdP integration/rotation untested |
| Hashed service keys | `security.py` | PBKDF2 roundtrip and prod-only policy | Env secrets + rotation operational responsibility |
| Audit integrity | `core._audit` | HMAC tamper detection | Must configure before first write; head must be externally anchored |
| Recovery | `backup.py`, `Fabric.backup` | Consistent backup and restore to a new DB | Cross-zone DR untested |
| MCP stdio | `mcp_server.py` | Tools have source implementations | MCP SDK not installed/tested end-to-end in validation runner |
| Google ADK | `integrations/google_adk` | Adapter provided | Google ADK runtime not tested here |
| Hooks | `hooks.py` | Opt-in, idempotency and sensitive-token filters | Generic partial hook; not complete native plugins |
| Benchmarks | `evaluate.py` | 12 documents, 8 questions, Recall@3 | No LongMemEval/LoCoMo, no AgentMemory baseline |
| CI | GitHub Actions YAML | Definition provided | Remote Actions status not known |
| Container | Dockerfile and Compose | Config/recipe authored | Docker deployment not executed in this environment |
| Horizontal scaling | **Not implemented** | — | Design and test Postgres+separate index |
| Encryption at rest | **Not implemented by SQLite code** | — | Encrypted volumes/backups required |
| Distributed rate limiting | **Not implemented** | — | Gateway/service mesh required |
| Compliance attestation | **Not performed** | — | Independent SOC2/ISO/GDPR assessments |

## What changed since v2

- Fail-closed production authentication, PBKDF2-verified keys and signed OIDC access tokens.
- Request correlation, readiness and authenticated aggregated process-local metrics.
- SQLite private creation mode, trusted schema disabled, secure delete flag and FULL synchronous writes.
- Explicit search candidate cap and filtered SQL candidate queries (no silent 500-row truncation).
- Online integrity-checked backups and verified restores to a **new** offline DB path.
- HMAC audit chaining/verification and production-mode UI disablement.
- Expanded MCP operations, safer opt-in capture and repeatable retrieval evaluation fixture.
- Added security regression coverage and production-pilot deployment/runbook documentation.

## Evidence

- Test command: `python -m pytest -q` (47 passed on the implementation branch before final packaging).
- Benchmark: `fabric-evaluate --fixture benchmarks/fixtures/coding-agent-mini.json --mode hybrid --k 3`.
- Packaging: `python -m pip wheel --no-deps --wheel-dir dist .`.

**Do not claim enterprise certification or comparative superiority based on this audit.**
