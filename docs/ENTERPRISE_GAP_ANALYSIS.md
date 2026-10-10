# Enterprise gap analysis and roadmap

## Complete in current release candidate

Single-node transactional memory API; explicit tenant/agent authorization; purpose, classification and sharing policies; typed memory layers; versioning; logical forgetting and holds; basic graph; BM25/vector/RRF retrieval; OIDC JWT signature/claim verification; hashed service keys; HMAC audit chains; backups; deterministic offline evaluation; CLI and REST; MCP and ADK adapter source.

## Release-blocking for broad enterprise production

1. **Distributed consistency/HA:** replace local SQLite authority with a transactionally safe multi-host design; implement schema migrations, leases, dead-letter queues and cross-region failover.
2. **External isolation controls:** cloud secret manager/KMS, TLS/mTLS ingress, per-tenant rate quotas, perimeter request-size limits, WAF, network policy and SIEM log export.
3. **Reliability:** load tests for 10K/100K/1M memories, 100+ concurrent clients, failover and recovery RPO/RTO, storage bloat, model resource usage and WAL contention.
4. **Agent UX:** native release-tested Claude/Cursor/Codex hooks, life-cycle event compatibility tests and safe context injection, beyond MCP configurations.
5. **Evaluation:** realistic, externally sourced long-memory benchmarks with apples-to-apples AgentMemory baselines, confidence intervals and cost/token metrics.
6. **Security assurance:** independent red team, dynamic/static analysis, third-party dependency scan, PII/data residency and compliance review.
7. **Secret, audit and deletion orchestration:** HMAC key rotation protocol, append-only external anchors, encrypted backups, end-to-end erasure confirmation from downstream projections.
8. **Operator experience:** observability dashboards, migration tooling, Helm chart, production alert rules, official support policy and tested rollback process.

Do not use the project as sole system of record for regulated or mission-critical workloads until these gaps are closed and independently reviewed.
