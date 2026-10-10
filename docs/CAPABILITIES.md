# Capabilities and limitations

The [README](../README.md) and [implementation audit](IMPLEMENTATION_AUDIT.md) are authoritative for v3.0.0-rc1. **Implemented** means source code exists; **verified** means tests were executed; **integrated** means exercised against a live third-party system; **enterprise-qualified** requires load, operational and independent security evidence.

| Domain | Feature | Present | Verified | Enterprise-qualified |
|---|---|---|---|---|
| Memory | Six typed, source-aware layers | Yes | Yes | No |
| Retrieval | BM25, hash/learned embeddings, RRF | Yes | Hash+BM25 | No |
| Graph | Explicit edges, ACL-safe traversal | Yes | Yes | No |
| Governance | Classification/purpose/grants, holds/forget | Yes | Yes | No |
| Identity | PBKDF2 and OIDC signature validation | Yes | Offline | No |
| Audit | HMAC-chain with verification | Yes | Yes | No |
| Operations | Backup, offline recovery, readiness | Yes | Yes | No |
| Clients | CLI, HTTP, MCP, Google ADK sample | Yes | Core CLI/HTTP | No |
| Deployment | Single-node non-root Compose | Yes | Not exercised | No |
| Distributed databases | PostgreSQL/Qdrant/Neo4j | No | No | No |
| Native auto-capture plugins | Claude/Cursor/Codex hooks | Generic hook only | Partial | No |

To propose a feature, attach tests and docs describing its limits. Do not add features to the README that exist only in the original architecture specification.
