# Agent Memory + Context Fabric


```text
Agent -> Context Manager -> [Working|Session|Episodic|Semantic|Entity|Procedural] -> Memory Policy -> ACL/Tenant Isolation -> Vector+Graph+SQL -> Retention/Forgetting/Audit
```

## Quick Start
```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8000/health
```

Write:
```bash
curl -X POST http://localhost:8000/v1/memories -H 'x-api-key: change-me' -H 'Content-Type: application/json' --data-binary @examples/write.json
```

Retrieve:
```bash
curl -X POST http://localhost:8000/v1/context -H 'x-api-key: change-me' -H 'Content-Type: application/json' --data-binary @examples/retrieve.json
```

## 1. Architecture

Agent -> Context Manager -> six memory layers -> policy -> ACL/tenant isolation -> SQL/vector/graph -> retention/forgetting/audit.

## 2. Six memory layers

Working is transient task context; Session is conversation continuity; Episodic stores events/outcomes; Semantic stores durable knowledge; Entity stores structured facts/relationships; Procedural stores approved ways of working.

## 3. Google alignment

Google Memory Bank publicly supports extraction, consolidation, asynchronous generation, event ingestion, similarity retrieval, identity-scoped isolation, TTL, revisions and IAM-conditioned access. Memory Profiles add schema-defined structured profiles.

## 4. Core invariant

Retrieved memory is context, never identity, permission, approval or authorization. Tool access must always be re-authorized against authenticated identity.

## 5. Write pipeline

Authenticate -> classify -> policy -> candidate extraction -> dedup/conflict search -> provenance validation -> retention -> SQL transaction -> revision/provenance/audit/outbox -> derived indexes.

## 6. Read pipeline

Authenticate -> trusted tenant -> ACL/classification/purpose/scope filtering -> candidate set -> semantic/lexical/graph ranking -> context budget -> audit. Security filtering happens before semantic ranking.

## 7. Provenance

Every memory tracks source type, source ID, agent, evidence, confidence and revision history. Source trust and model confidence are separate concepts.

## 8. Conflict handling

Classify duplicate, compatible extension, newer replacement, contradiction, temporal change and scope difference. Never silently overwrite consequential memory; create revisions and preserve provenance.

## 9. Temporal truth

Use valid_from/valid_to/observed_at/version semantics for facts that change over time.

## 10. Structured profiles

Profiles use fixed schemas for low-latency initialization. Keep one logical profile per schema/scope while preserving field-level revisions and provenance.

## 11. SQL

SQL is authoritative for content metadata, revisions, ACLs, provenance, share grants, retention, audit and outbox.

## 12. Vector store

Vector search is a derived retrieval projection. Apply trusted tenant/scope filters before ranking; persist embedding model/version and support versioned re-embedding.

## 13. Graph store

Graph memory represents entities and relationships. Traversal must remain tenant/ACL constrained.

## 14. Redis

Use Redis for working/session cache, rate limits and retrieval caches—not as the only durable source of truth.

## 15. Transactional outbox

Commit memory state and index/audit event intent atomically. Consumers update vector/graph projections idempotently.

## 16. Cross-agent sharing

Use explicit, narrow, expiring share grants constrained by tenant, source agent, destination agent, layers and scope. Working memory is private by default.

## 17. Memory poisoning

Defend with trusted write paths, provenance, classification, conflict checks, procedural-memory review, anomaly detection and revision history.

## 18. Prompt injection

Stored instructions such as 'ignore policy' remain untrusted data and cannot change IAM, ACLs or credentials.

## 19. Retention

Retention varies by layer, classification, purpose, tenant and jurisdiction. TTL expiration must propagate to derived indexes/caches.

## 20. Forgetting

Authorize -> tombstone authoritative memory -> outbox event -> purge vector/graph/cache -> audit -> reconcile. Regulatory hard deletion can follow policy.

## 21. Legal hold

Legal hold can supersede ordinary TTL/deletion when authorized and legally required.

## 22. Audit

Audit creates, reads for sensitive scopes, shares, revisions, forgets and administrative policy changes.

## 23. Purpose limitation

A memory authorized for one purpose is not automatically authorized for another.

## 24. Data minimization

Persist only useful, stable information needed for the declared purpose.

## 25. Entity resolution

Use canonical IDs, aliases and provenance-preserving merges for entity memory.

## 26. Context assembly

Return memory IDs and provenance with context so downstream answers/actions are traceable.

## 27. Authorization boundary

Memory cannot satisfy current human approval or grant tool permissions. IAM/policy services remain authoritative.

## 28. Multi-tenancy

Scope SQL, vectors, graph edges, Redis keys, events, logs and metrics by trusted tenant context.

## 29. Multi-region

Choose an authoritative home region or use explicit optimistic concurrency/versioning. Avoid destructive last-write-wins.

## 30. Replication conflicts

Use expected versions/ETags or serialized ownership for concurrent profile/memory updates.

## 31. SLOs

Measure write durability, retrieval availability/latency, index freshness, forget propagation and audit completeness.

## 32. Observability

Trace extraction, consolidation, policy, SQL, vector search, graph expansion and context assembly with run/tenant/memory IDs.

## 33. Security testing

Test cross-tenant access, cross-agent access, classification bypass, prompt injection, poisoning, expired grants and forgotten-memory retrieval.

## 34. Chaos testing

Kill index consumers, lose Redis/vector/graph services, restart SQL and prove authoritative recovery.

## 35. DR

Restore SQL, replay outbox, rebuild vector/graph projections, invalidate caches and verify ACL/forget invariants before reopening.

## 36. Applications

Personal assistants, engineering agents, research agents, support, incident response, CRM and multi-agent teams can use the same fabric with different schemas/policies.

## 37. Personal assistant

Remember stable preferences across sessions without acquiring extra authority.

## 38. Engineering agent

Store architecture decisions, incidents, repository entities and reviewed team procedures.

## 39. Research agent

Consolidate findings while retaining citations, contradictions and source trust.

## 40. Support agent

Remember customer context inside tenant/user scope; CRM permissions remain external.

## 41. Incident response

Use episodic memory for prior incidents and procedural memory for reviewed runbooks.

## 42. Profile versioning

Version profile schemas and maintain field provenance during migrations.

## 43. Re-embedding

Write vectors to a new index/model version, dual-read during migration, validate recall, then cut over.

## 44. Hot scopes

Shard/cache carefully for users/projects with very large memory collections; enforce context budgets.

## 45. Cost governance

Track extraction/model cost, embedding/index operations, vector/graph queries and storage by tenant.

## 46. Rate limiting

Limit writes, generation, retrieval, sharing and administrative operations per tenant/principal/agent.

## 47. Kubernetes

Separate API, extractor, consolidator, retrieval, indexers, retention, forget, audit and reconciliation workers. Use workload identity and deny-by-default networking.

## 48. Production services

memory-api; session-ingestor; extractor; consolidator; conflict-resolver; policy; profile-service; retrieval; context-manager; vector-indexer; graph-indexer; retention-worker; forget-worker; audit-exporter; outbox-publisher; reconciliation-worker.

## 49. Production upgrade path

Add OIDC/workload identity, Alembic, full ACL/share APIs, Qdrant filtered adapter, Neo4j adapter, Redis layers, Kafka workers, extraction/model gateway, semantic conflict resolution, profile service, optimistic concurrency, lifecycle workers, DLP, OTel, Helm, multi-region and DR tests.

## 50. Principal design questions

Why pre-filter before vector ranking? How represent temporal truth? How resolve trustworthy contradictions? How forget across projections? How share memory without leaking working state? How re-embed at scale? Why can memory never authorize?

## Full local run instructions

```bash
docker compose up -d postgres redis qdrant neo4j redpanda
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# change service hostnames in .env to localhost
uvicorn app.main:app --reload
pytest -q
ruff check .
```

Database:
```bash
docker compose exec postgres psql -U postgres -d memory
```

Inspect:
```sql
\dt
SELECT * FROM memories;
SELECT * FROM memory_revisions;
SELECT * FROM provenance;
SELECT * FROM memory_acl;
SELECT * FROM share_grants;
SELECT * FROM audit;
SELECT * FROM outbox;
```

## Production API target

```text
POST /v1/memories
GET /v1/memories/{id}
GET /v1/memories/{id}/revisions
POST /v1/memories/generate
POST /v1/memories/consolidate
POST /v1/context
POST /v1/profiles
GET /v1/profiles/{schema}/{scope}
POST /v1/share-grants
DELETE /v1/share-grants/{id}
POST /v1/memories/{id}/forget
GET /v1/audit
```

## Code walkthrough

`domain.py` defines six layers and request contracts. `models.py` provides durable SQL memory/revision/provenance/ACL/share/audit/outbox foundations. `policy.py` performs tenant/classification/scope/agent checks. `embeddings.py` is a deterministic offline embedding so the reference runs without an external model. `conflicts.py` finds overlap candidates without destructive overwrite. `retention.py` assigns TTL. `memory_store.py` transactionally writes memory + revision + provenance + audit + outbox. `retrieval.py` applies security before ranking. `context_manager.py` explicitly marks memory as non-authoritative context. `sharing.py` protects working memory. `forgetting.py` tombstones authoritative state and emits purge intent.

## Production readiness matrix

| Area | Reference | Production |
|---|---|---|
| SQL memory/revisions | executable | Alembic + RLS |
| Provenance | executable | signed/richer evidence |
| Tenant filtering | executable | trusted OIDC/workload identity |
| Vector | local deterministic ranking | Qdrant/managed vector filtered adapter |
| Graph | architecture | Neo4j/managed graph adapter |
| Conflict | candidate detection | semantic + policy consolidation |
| Profiles | architecture | schema/profile service |
| Retention | TTL assignment | lifecycle workers |
| Forget | tombstone/outbox | vector/graph/cache purge + reconciliation |
| Cross-agent | policy model | durable grants + APIs |
| Events | outbox + Redpanda infra | publisher/consumers |
| Observability | design | OpenTelemetry |
| Kubernetes | starter | hardened Helm/platform |

## Final architecture rule

```text
Source       -> evidence
Extractor    -> candidate memory
Policy       -> whether it may exist/be seen
Conflict     -> relationship to prior memory
SQL          -> durable truth + revisions
Vector       -> semantic retrieval
Graph        -> relationships
ACL          -> visibility
Context      -> authorized bounded package
Agent        -> reasoning
IAM/Policy   -> authority, separately
Retention    -> lifetime
Audit        -> reconstruction
```

**Memory can inform an agent. Memory must never authorize an agent.**



# Comprehensive Production Engineering Guide

## 50. Full production topology

```text
                         AGENTS / APPLICATIONS
                                  |
                         Context Fabric API
                                  |
                    Identity / Tenant / Purpose
                                  |
                 +----------------+----------------+
                 |                                 |
             WRITE PATH                         READ PATH
                 |                                 |
       Candidate Extraction                 Context Request
                 |                                 |
       Classification / DLP                 Policy / ACL Gate
                 |                                 |
       Conflict Candidate Search           Authorized Corpus
                 |                                 |
       Consolidation Policy               Hybrid Retrieval
                 |                         /      |       \
       Provenance Validation           Vector   Graph   Lexical
                 |                         \      |       /
       Retention Policy                    Reranking
                 |                             |
       SQL Transaction                    Context Budget
       /      |       \                        |
 Memory   Revision   Outbox             Context Bundle
   |         |          |                    |
   |         |          +----> Event Bus     |
   |         |                    |           |
   |         |              +-----+-----+     |
   |         |              |           |     |
   |         |          Vector Index  Graph Index
   |         |              |           |
   +---------+--------------+-----------+
                                  |
                     Retention / Forget / Audit
```

## 51. Trust boundaries

The system has explicit trust boundaries around authenticated principals, model output, memory content, source documents, vector results, graph results, external tools, administrators and derived indexes. A memory record is never promoted into the trusted identity boundary.

## 52. Principal model

A production principal should contain authenticated tenant, subject, workload/agent identity, roles, groups, delegation chain, authentication strength and request purpose. Tenant IDs supplied in JSON bodies are not trusted.

## 53. Workload identity

Production agents should use workload identity rather than static API keys. Local `x-api-key` authentication exists only to keep the reference runnable.

## 54. RBAC + ABAC

RBAC answers broad capability questions; ABAC evaluates tenant, subject, agent, project, purpose, classification, geography and resource attributes.

## 55. Policy decision

A policy result should be explicit:

```json
{
  "decision": "ALLOW",
  "policy_version": "2026-10-01",
  "reason_codes": ["SAME_TENANT", "PROJECT_MEMBER"],
  "obligations": ["AUDIT_READ"],
  "expires_at": "..."
}
```

## 56. ACL inheritance

Project/team memories may inherit access from their owning scope, while explicit deny rules override inherited grants.

## 57. Authorization cache

Cache only policy decisions with a short TTL and include principal, resource version, purpose and policy version in the cache key.

## 58. Retrieval side channels

Unauthorized memories must not affect scores, result counts, latency-sensitive metadata or explanations exposed to callers.

## 59. Candidate extraction service

Extraction converts raw events into typed candidate memories. It should output structured claims, source spans, confidence, sensitivity and proposed scope.

## 60. Extraction is proposal, not truth

The extractor is an untrusted producer. Policy and consolidation decide whether the candidate becomes durable memory.

## 61. Consolidation service

The consolidator compares a candidate with same-scope authorized existing memories and chooses create, merge, revise, supersede, reject or human-review.

## 62. Conflict decision record

Persist conflict decisions so operators can reconstruct why a memory changed.

## 63. Source hierarchy

Organizations may define source trust such as:

```text
signed system-of-record event
> approved enterprise document
> verified human statement
> ordinary tool output
> model inference
> untrusted external content
```

This hierarchy is policy, not a universal truth.

## 64. Confidence calibration

Do not treat raw LLM confidence as calibrated probability. Use evaluation-derived confidence bands and source trust separately.

## 65. Claim granularity

Prefer atomic claims over large narrative blobs when facts need independent revision, retention or ACLs.

## 66. Memory normalization

Normalize dates, canonical entity IDs, units and known enumerations before conflict analysis.

## 67. Memory deduplication

Use content hash for exact duplicates and semantic/graph matching for near duplicates.

## 68. Contradiction resolution

For consequential contradictions, preserve both claims, source evidence and temporal scope until deterministic policy or authorized review resolves them.

## 69. Supersession

Superseding a memory changes its active validity; it does not erase historical provenance.

## 70. Bitemporal model

For high-value memory, distinguish when a fact was valid in the world from when the system learned it.

## 71. Profile service

The profile service materializes schema-defined views over memories for fast agent initialization.

## 72. Profile schema registry

Schemas are versioned, validated and tenant/application scoped.

## 73. Field-level profile ACL

A profile may contain fields with different sensitivity. Apply access controls at field level when needed.

## 74. Profile update concurrency

Use expected-version/ETag checks to prevent lost updates.

## 75. Working memory implementation

Working memory should be small, short-lived and tied to an active task/run. Redis is appropriate for this layer.

## 76. Session memory implementation

Session memory preserves conversation continuity and tool/action summaries. It can be durable but has a separate lifecycle from long-term memory.

## 77. Episodic implementation

Episodes should include event time, actors, outcome, evidence and links to related entities.

## 78. Semantic implementation

Semantic memory stores durable claims/knowledge with provenance and temporal validity.

## 79. Entity implementation

Entity memory uses canonical IDs and graph relationships, with SQL metadata for policy/provenance.

## 80. Procedural implementation

Procedures require versioning, stronger review and explicit supersession because they directly shape future agent behavior.

## 81. Memory promotion

A useful lifecycle is:

```text
working -> session -> candidate long-term -> reviewed/consolidated -> semantic/episodic/entity/procedural
```

Promotion is policy-driven, never automatic simply because content appeared repeatedly.

## 82. Memory demotion

Stale or low-value memories can become inactive before physical deletion.

## 83. Hybrid retrieval pipeline

```text
request
 -> authorization filter
 -> metadata filter
 -> lexical candidates
 -> vector candidates
 -> graph expansion
 -> fusion
 -> provenance/trust weighting
 -> temporal weighting
 -> diversity
 -> context-budget selection
```

## 84. Reciprocal rank fusion

RRF can combine lexical/vector rankings without assuming score calibration across retrieval systems.

## 85. Graph expansion

Graph expansion is bounded by hop count, edge type, tenant and ACL.

## 86. Diversity

Avoid returning ten semantically duplicate memories. Use MMR or claim/entity diversity.

## 87. Context budget allocator

Allocate token budgets by layer and task. For example, procedural memory may receive priority during an operational task.

## 88. Citation to memory

Agent outputs can retain memory IDs so a UI/audit system can explain which memories informed the answer.

## 89. Freshness

Use temporal validity and source freshness, not just insertion time.

## 90. Negative memory

Represent known-invalid or superseded claims explicitly so they are not rediscovered as active truth.

## 91. Retention worker

A scheduled worker identifies expired memories, changes authoritative state and emits projection-purge events.

## 92. Forget worker

Explicit forgetting has higher urgency than ordinary expiration and should have a measurable propagation SLO.

## 93. Projection deletion

Vector and graph deletion is asynchronous but reconciled. The read path must honor authoritative forgotten status even during propagation delay.

## 94. Cache invalidation

Forget/revision/share-grant events invalidate relevant caches by tenant/scope/version.

## 95. Backup and deletion

Backups complicate deletion. Define backup retention and cryptographic/physical erasure procedures consistent with policy.

## 96. Encryption

Use TLS in transit and managed encryption at rest. For high-sensitivity tenants, consider tenant-specific encryption keys.

## 97. Key rotation

Rotation must not require rewriting semantic meaning; encryption metadata is independent of memory content.

## 98. DLP

Run DLP/classification before durable storage and again before cross-boundary sharing where required.

## 99. Secret handling

Secrets should generally not become long-term agent memory. Detect and reject/redact credentials, private keys and tokens.

## 100. Prompt injection handling

Memory content is wrapped/tagged as untrusted contextual data. System/developer/policy instructions remain structurally separate.

## 101. Memory poisoning anomaly detection

Watch for unusual write rates, repeated attempts to alter procedural memory, conflicting claims from low-trust sources and cross-scope write patterns.

## 102. Administrative controls

Admins can inspect policy, revoke share grants, quarantine memory, trigger reindex, force retention and export audit—but should not bypass tenant boundaries without explicit privileged workflow.

## 103. Quarantine

Suspicious memory can enter `QUARANTINED`, making it unavailable to normal retrieval while preserving evidence.

## 104. State machine

```text
CANDIDATE
 -> ACTIVE
 -> SUPERSEDED
 -> EXPIRED
 -> FORGOTTEN

CANDIDATE -> QUARANTINED
ACTIVE -> QUARANTINED
QUARANTINED -> ACTIVE / FORGOTTEN
```

## 105. Revision state

A revision is immutable. "Current" is a pointer/state relationship, not mutation of historical evidence.

## 106. SQL transaction boundary

Memory, revision, provenance, audit and outbox should commit atomically.

## 107. Outbox publisher

A publisher uses `FOR UPDATE SKIP LOCKED` or equivalent to claim unpublished events, publishes them and marks them delivered.

## 108. Event topics

```text
memory.created
memory.revised
memory.superseded
memory.expired
memory.forgotten
memory.quarantined
memory.share.changed
profile.changed
```

## 109. Event ordering

Partition by tenant + logical memory/profile scope where ordering matters.

## 110. Idempotency

Consumers store processed event IDs or use deterministic projection versions.

## 111. Vector projection

A vector record contains memory ID, version, tenant, allowed scope metadata, embedding version and active state.

## 112. Graph projection

Graph nodes/edges contain authoritative IDs and version metadata so stale projections can be detected.

## 113. Reconciliation

Periodically compare SQL authoritative versions to derived vector/graph projections and repair missing/stale/deleted entries.

## 114. Re-embedding architecture

```text
SQL active memories
 -> new embedding workers
 -> vector index v2
 -> quality validation
 -> dual read/shadow
 -> cutover
 -> retire v1
```

## 115. Large-scale re-embedding

Throttle by tenant, use checkpoints, batch requests and make the operation restartable.

## 116. Graph rebuild

Because graph is derived, rebuild it from authoritative entity/relationship memories and provenance.

## 117. Session ingestion

Session/tool events should enter a durable stream. Extraction can operate asynchronously and independently of interactive response latency.

## 118. Backpressure

If extraction/indexing falls behind, protect the interactive read/write API and expose index freshness metrics.

## 119. Dead-letter queues

Malformed or repeatedly failing events enter a DLQ with enough metadata for replay.

## 120. Rate limits

Rate-limit write, generation, retrieval, share, forget and admin operations separately.

## 121. Quotas

Quotas can cover active memories, storage bytes, vector count, profile count, writes/day and retrieval QPS.

## 122. Fairness

Large tenants should not starve smaller tenants' indexing or retention work.

## 123. Cost accounting

Attribute model extraction, embeddings, vector search, graph queries, SQL, cache and event costs per tenant/application.

## 124. API idempotency

Create/generate/forget/share operations accept idempotency keys.

## 125. API pagination

List/revision/audit APIs use stable cursor pagination.

## 126. API optimistic concurrency

Update endpoints accept `If-Match`/expected version.

## 127. API error model

Use machine-readable codes such as:

```text
TENANT_MISMATCH
ACL_DENIED
CLASSIFICATION_DENIED
STALE_VERSION
MEMORY_FORGOTTEN
SHARE_EXPIRED
CONFLICT_REVIEW_REQUIRED
```

## 128. Memory generation API

A generation request should return a job ID for asynchronous extraction/consolidation.

## 129. Job status

Expose state, progress, error class, created/revised memory IDs and audit references.

## 130. Read-your-writes

If required, direct retrieval can consult authoritative SQL until derived indexes reach the committed version.

## 131. Eventual consistency

Document where vector/graph/profile projections are eventually consistent and expose freshness.

## 132. Consistency tokens

A write can return a committed memory version; a subsequent read may request at-least-that version.

## 133. Multi-region strategy

Prefer single-writer ownership per logical memory/profile scope unless conflict semantics are explicitly implemented.

## 134. Region routing

Route by tenant residency and logical scope owner.

## 135. Failover

Fence the old writer region, promote authoritative SQL, resume event consumers, reconcile projections, then restore writes.

## 136. Split brain

Never allow two regions to silently perform last-write-wins on the same high-value profile.

## 137. Observability traces

Trace:

```text
memory.write
memory.extract
memory.conflict
memory.consolidate
memory.policy
memory.retrieve
memory.vector
memory.graph
memory.context
memory.forget
memory.reconcile
```

## 138. Metrics

Track p50/p95/p99 retrieval latency, write latency, denied reads, conflicts, index lag, forget lag, stale projections, context tokens and source-trust distribution.

## 139. Logs

Structured logs include tenant, principal, agent, memory ID, revision, policy version, trace ID and action—never raw secrets.

## 140. Audit export

Export audit to immutable/compliance storage independently of operational SQL retention.

## 141. SLO example

```text
99.95% authorized retrieval availability
p95 retrieval < 300 ms for profile + bounded memory search
99% vector projection freshness < 30 s
99% forget propagation < 5 min
100% sensitive reads auditable
```

Targets depend on deployment and scale.

## 142. Alerting

Alert on index lag, forget lag, ACL denial spikes, poisoning signals, outbox backlog, DLQ growth and reconciliation mismatch.

## 143. Capacity model

Estimate:

```text
active memories
average bytes/memory
embedding dimensions
writes/sec
retrieval QPS
graph edges/entity
retention churn
profile size
```

## 144. Performance optimization

Use connection pools, batched embeddings, filtered ANN, graph query limits, profile caching and asynchronous projection.

## 145. Hot-user problem

Shard/cache high-volume subjects and cap per-request candidate retrieval before reranking.

## 146. Vector cardinality

Partition/filter indexes using tenant/scope metadata while balancing index fragmentation.

## 147. SQL partitioning

At large scale, partition audit/event/history tables by time and possibly tenant class.

## 148. Testing pyramid

```text
unit
policy property tests
repository/integration
vector/graph contract
event/outbox
security
load
chaos
DR
```

## 149. Tenant isolation property

For all principals and memories where tenant differs, retrieval must return false regardless of semantic similarity.

## 150. Forgotten-memory property

A forgotten memory must never appear in context even if its stale vector remains temporarily.

## 151. Authorization property

No memory content can mutate principal roles, ACLs or policy decisions.

## 152. Revision property

Every active revision has an intact provenance chain.

## 153. Cross-agent property

No agent-private memory crosses agents without a valid grant or explicit privileged role.

## 154. Conflict tests

Test exact duplicate, paraphrase, temporal replacement, contradictory source, different scope and same entity/different attribute.

## 155. Security red-team

Attempt memory prompt injection, privilege claims, credential storage, tenant spoofing, graph traversal leakage and vector-filter bypass.

## 156. Load test

Generate realistic tenant distributions rather than uniform random IDs.

## 157. Chaos test

Stop Qdrant/Neo4j/Redis/Kafka independently and verify SQL-authoritative safety behavior.

## 158. DR test

Restore SQL into a clean environment, replay outbox/history, rebuild projections and prove security invariants.

## 159. CI/CD

Run lint, unit, policy properties, integration, migration checks, image scan, SBOM, signature and deployment-policy checks.

## 160. Database migrations

Use Alembic expand/contract migrations; never rely on `create_all` in production.

## 161. Deployment

Production components:

```text
API
Policy Service
Profile Service
Extractor Workers
Consolidation Workers
Vector Indexers
Graph Indexers
Retention Workers
Forget Workers
Outbox Publisher
Reconciliation Workers
Audit Exporter
```

## 162. Kubernetes security

Use workload identity, non-root containers, read-only root filesystems, seccomp, resource limits, PodDisruptionBudgets and deny-by-default NetworkPolicies.

## 163. Secrets

Use a secret manager/workload identity. Never commit production credentials to `.env`.

## 164. Helm

A production chart should expose replicas, autoscaling, resource classes, service endpoints, policy versions, residency and observability configuration.

## 165. Autoscaling

Scale retrieval on QPS/latency, indexers on consumer lag, extraction on event backlog and lifecycle workers on queue age.

## 166. Graceful shutdown

Workers stop claiming new work, finish/ checkpoint current batches and commit offsets safely.

## 167. Application: enterprise coding assistant

Store repository entities, reviewed architectural decisions and past incident outcomes. Keep transient chain-of-thought/working context out of long-term shared memory.

## 168. Application: SRE agent

Episodic memory captures incidents; procedural memory stores approved runbooks; entity memory maps services/dependencies.

## 169. Application: research platform

Semantic memories preserve claims/citations; conflict resolution explicitly represents disagreement.

## 170. Application: customer support

Profile memory captures stable preferences/account context while policy prevents cross-customer retrieval.

## 171. Application: sales copilot

Structured profiles provide account context while CRM remains the authority for permissions and live business facts.

## 172. Application: multi-agent software engineering

Research, coding, test and review agents share project-approved semantic/entity memory but keep private working memory separate.

## 173. Application: enterprise knowledge assistant

Consolidate knowledge across sessions/documents while preserving source provenance and document ACLs.

## 174. Application: incident commander

Context assembly combines active incident state, relevant past episodes, service graph and approved procedures.

## 175. Application: workflow agent

Procedural memory stores reviewed workflow patterns; live tool permissions are checked independently.

## 176. Application: regulated environments

Use stronger DLP, consent, residency, audit, retention, purpose limitation and human review.

## 177. Anti-pattern: vector DB equals memory

A vector DB is a retrieval index, not a memory governance system.

## 178. Anti-pattern: retrieve then ACL filter

This risks leakage and side channels. Filter before ranking.

## 179. Anti-pattern: last write wins

It destroys provenance and can turn poisoning into durable truth.

## 180. Anti-pattern: all chat turns become memory

This creates noise, privacy risk and high retrieval cost.

## 181. Anti-pattern: memory grants permission

This is a privilege-escalation vulnerability.

## 182. Anti-pattern: delete only from vector DB

Authoritative SQL and every projection/cache must follow the lifecycle decision.

## 183. Anti-pattern: global shared agent memory

Sharing must be scoped and explicit.

## 184. Anti-pattern: unversioned embeddings

Without embedding version metadata, migrations and reproducibility become unsafe.

## 185. Anti-pattern: procedural memory without review

A poisoned procedure can influence many future actions.

## 186. Code mapping

```text
app/domain.py          -> memory/principal contracts
app/models.py          -> SQL truth, revisions, ACL, provenance, audit, outbox
app/policy.py          -> tenant/classification/scope enforcement
app/embeddings.py      -> offline deterministic retrieval embedding
app/conflicts.py       -> overlap/conflict candidate detection
app/retention.py       -> TTL policy
app/memory_store.py    -> atomic write transaction
app/retrieval.py       -> policy-before-ranking retrieval
app/context_manager.py -> bounded non-authoritative context
app/sharing.py         -> cross-agent guardrails
app/forgetting.py      -> authoritative forget transition
app/api.py             -> HTTP surface
```

## 187. Why deterministic embeddings are included

The repository is runnable without requiring paid credentials. The deterministic embedding is a local development adapter, not a claim of production semantic quality.

## 188. Production vector adapter

Replace the local ranking adapter with Qdrant/Vertex/pgvector using server-side tenant/scope filters and embedding-version metadata.

## 189. Production graph adapter

Replace the graph abstraction with Neo4j/managed graph while preserving trusted tenant/ACL predicates.

## 190. Production extraction adapter

Use an approved model gateway with structured JSON output, schema validation, prompt versioning, retries and evaluation.

## 191. Production conflict classifier

Combine deterministic temporal/source rules with a semantic classifier. Deterministic policy remains authoritative for security.

## 192. Production policy adapter

Integrate enterprise IAM/OPA/Cedar-style policy and preserve policy version/reason codes in audit.

## 193. Production audit adapter

Stream sensitive audit events to immutable storage/SIEM.

## 194. Run: Docker

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
```

## 195. Run: host development

```bash
docker compose up -d postgres redis qdrant neo4j redpanda

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# For host execution, change postgres/qdrant/neo4j/redpanda/redis
# hostnames in .env to localhost.

uvicorn app.main:app --reload
```

## 196. Run: create memory

```bash
curl -X POST http://localhost:8000/v1/memories \
  -H 'x-api-key: change-me' \
  -H 'Content-Type: application/json' \
  --data-binary @examples/write.json
```

## 197. Run: retrieve context

```bash
curl -X POST http://localhost:8000/v1/context \
  -H 'x-api-key: change-me' \
  -H 'Content-Type: application/json' \
  --data-binary @examples/retrieve.json
```

## 198. Run: tests

```bash
pytest -q
ruff check .
```

## 199. Run: inspect SQL

```bash
docker compose exec postgres psql -U postgres -d memory
```

```sql
\dt
SELECT * FROM memories;
SELECT * FROM memory_revisions;
SELECT * FROM provenance;
SELECT * FROM memory_acl;
SELECT * FROM share_grants;
SELECT * FROM audit;
SELECT * FROM outbox;
```

## 200. Run: service logs

```bash
docker compose logs -f api
docker compose logs -f postgres
docker compose logs -f qdrant
docker compose logs -f neo4j
docker compose logs -f redpanda
```

## 201. Run: clean local environment

```bash
docker compose down
```

Use `docker compose down -v` only when intentionally deleting local database/index volumes.

## 202. Kubernetes starter

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/api.yaml
```

The included Kubernetes files are starters, not a claim of a complete production cluster.

## 203. Production readiness checklist

```text
[ ] OIDC/workload identity
[ ] trusted tenant derivation
[ ] Alembic migrations
[ ] complete ACL/share-grant APIs
[ ] row-level security defense in depth
[ ] production vector adapter
[ ] production graph adapter
[ ] extraction/consolidation workers
[ ] transactional outbox publisher
[ ] Kafka consumers
[ ] index reconciliation
[ ] profile service
[ ] optimistic concurrency
[ ] retention worker
[ ] complete forget propagation
[ ] DLP/classification
[ ] audit export
[ ] OTel traces/metrics
[ ] rate limits/quotas
[ ] security/property tests
[ ] load/chaos tests
[ ] backup/restore
[ ] multi-region/residency
[ ] hardened Kubernetes/Helm
```

## 204. Principal-level system-design review

```text
Why SQL is authoritative and vector/graph are projections.
Why authorization must precede similarity search.
Why source trust differs from model confidence.
Why contradictions require temporal/provenance semantics.
Why working memory is not globally shareable.
Why procedural memory needs stronger governance.
Why forgetting is a distributed workflow.
Why outbox + idempotency + reconciliation beat "exactly once".
Why memory cannot grant tool authority.
How re-embedding works without downtime.
How multi-region profile conflicts are prevented.
How derived indexes recover from disaster.
```

## 205. Final invariant

```text
Authenticated Identity -> establishes who is acting
Policy / ACL           -> establishes what may be accessed
Memory                 -> provides contextual evidence
Agent                  -> reasons over that evidence
IAM / Approval         -> authorizes actions
Audit                  -> reconstructs decisions
```

**Memory can change what an agent knows. It must not change what the agent is authorized to do.**
