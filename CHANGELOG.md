# Changelog

## v3.0.0-rc1 — 2026-10-09

### Added
- Production-mode fail-closed authentication; hashed PBKDF2 service keys and asymmetric OIDC/JWKS with issuer, audience, expiration, role and tenant allowlist checks.
- HMAC-chained audit metadata and tenant-level verification; backward-compatible schema migration (historical rows unsealed).
- SQLite safe backup, restore-to-new, integrity inspection and WAL checkpoint CLI.
- Lexical/hybrid/vector retrieval modes, scoped SQL candidate queries and explicit candidate caps.
- Safe opt-in hook ingestion, credential-pattern filtering, idempotency and hashed session IDs.
- Expanded MCP tool surface for governance, graph, profiles, history and integrity.
- Correlated API request IDs, readiness, authenticated aggregate metrics and no-store security headers.
- Reproducible top-k mini evaluator, security regression tests, production-pilot Compose and extensive operations/security documentation.

### Limitations
- Still SQLite single-node, no HA, unverified MCP/ADK end-to-end, no comparative AgentMemory or real-world benchmark evidence.

## v2.0.0 — 2026-10-09

- Local first executable memory store, six layers, policy, revisions, graph, retention, MCP/ADK adapters, CLI, HTTP and 34 original automated tests.
- Original attached repository preserved in `legacy/` and `docs/ORIGINAL_README.md`.
