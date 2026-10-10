# Operations runbook — v3.0.0-rc1

This runbook is for an **isolated single-node pilot**. It is not a multi-zone SLA plan.

## 1. Prepare

- Provision Python >=3.11 or build the Dockerfile image with patched OS/Python dependencies.
- Restrict access to the data directory (0700) and database (0600); do not share it over unsafe network filesystems.
- Store a hashed service verifier or configure IdP JWKS allowlists. Reject raw keys in production.
- Generate `FABRIC_AUDIT_HMAC_KEY` (32+ bytes), store it in a secret manager and configure it **before first write**.
- Configure TLS gateway, request size caps, IP/service rate limits and authn monitoring.
- Design storage encryption, backup encryption, retention and privacy incident response.

## 2. Start and observe

```bash
python -m pip install -e '.[server]'
FABRIC_MODE=production fabric serve --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Compose: `docker compose --env-file .env.production -f deploy/compose.production.yml up --build -d`. Production mode will refuse startup without hashed credentials or configured OIDC. Only one worker should be launched per SQLite authority on this architecture.

`GET /metrics` is admin-only and returns process-local aggregate counts; instrument your gateway for distributed metrics, traffic rates and percentile latencies. Do not label metrics with tenant or memory IDs.

## 3. Backups and restore

```bash
fabric --db /secure/data/memory.sqlite verify
fabric --db /secure/data/memory.sqlite backup /secure/backups/snapshot.sqlite
# Off-host: encrypt and upload through an approved backup tool.

# For recovery, stop your API/worker first and work in a separate environment.
fabric restore-to-new /secure/backups/snapshot.sqlite /secure/restored/memory.sqlite
fabric --db /secure/restored/memory.sqlite verify
```

Recovery is manual. **Never** copy a live `*.sqlite` file with plain `cp` while WAL writes are happening. Use the SQLite backup API above. Verify the recovered DB, file permissions and authorized memories. Then point the stopped service to the restored path and restart; do not overwrite existing WAL/shm files. Set RPO/RTO targets appropriate to your backup frequency and practice them regularly. Clean old backups using approved secure retention policies.

## 4. Scheduled retention

Run `fabric --tenant ... --roles admin --db /path/to/db sweep` for each tenant from a trusted scheduler. This scrubs expired memories not under hold. Verify outbox, graph/links and backup retention after large deletions. Use `fabric ... checkpoint` only during a controlled maintenance window; it can report busy if readers are active.

## 5. Audit verification and anchoring

```bash
fabric --tenant my-tenant --roles admin --db /secure/data/memory.sqlite audit-verify
```

Export the `head_mac` to immutable off-host storage at regular intervals. The MAC chain does not by itself detect tail truncation; store/rotate keys in KMS with access logging. Any unsealed historical audit rows are explicitly reported. Do not publish the HMAC key.

## 6. Incident playbooks

**Compromised service token:** Revoke/remove its verifier, restart, identify the tenant/agent, inspect access metadata and rotate any secondary credentials. Static keys do not support fine-grained online revocation without a configuration reload.

**Cross-tenant leakage:** Disable ingress, preserve logs, verify claim mapping + grants, identify potentially affected records and treat as a security incident. Do not assume audit metadata proves absence of reads from direct database access.

**SQLite corruption:** Stop writers, preserve encrypted forensic copy, execute `fabric verify`, restore known-good backup to a **new** file, run integrity tests and audit recovery gaps before service restart.

**Slow retrieval / memory pressure:** Inspect candidate counts, narrow scope, pin embedding model, reduce `FABRIC_SEARCH_MAX_CANDIDATES` appropriately, measure p95 and plan migration to indexed retrieval.

## 7. Exit criteria for enterprise production

Real identity-provider rotation/expiry testing; infrastructure rate-limit/TLS tests; backup restore drill; corruption/failover drill; penetration test; distributed architecture implementation for multi-host targets; quantified SLO and load testing; privacy/legal review; operator on-call handoff.
