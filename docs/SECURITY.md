# Security architecture and limitations

## Threat model

**Actors:** authenticated agents, tenant administrators, compromised API keys, malicious agent-generated memory text, insiders with database files, external internet callers, and compromised deployment proxies.

**Trust:** trusted HTTP gateway + IdP; `security.authenticate`; `Principal`; core ACL checks. Untrusted: API request JSON, LLM messages, recalled memory text, client-supplied scope and external MCP hook payloads. A local process with unrestricted SQLite write access can bypass this policy engine; file and OS isolation are essential.

## Authentication

- `FABRIC_MODE=production` blocks the legacy plaintext `FABRIC_API_KEY` and `FABRIC_CREDENTIALS_JSON` mechanisms.
- Hashed service credential config uses PBKDF2-HMAC-SHA256 + independent salt; verification is constant-time for the digest.
- OIDC uses PyJWT with HTTPS issuer/JWKS, `RS256` or `ES256`, exact audience and issuer verification, required expiration/issued-at/subject claims, allowlisted tenant, role intersection and maximum clearance.
- `FABRIC_OIDC_ALLOWED_ROLES` should normally be **empty** or contain only least-privileged roles. `admin`, `all_purposes`, `tenant_reader`, and `procedure_approver` are privileged policy actions; granting them requires an IdP review.
- JWKS availability and key rotation behavior need testing with your identity provider; service tokens cannot be globally revoked offline before their `exp` unless gateway/IdP revocation mechanisms are added.

## Authorization

Tenant conditions are added to object queries. `_base_access` enforces agent ownership or current grant, classification ceilings, purpose equality, scope match and time-window validity. `tenant_reader` bypasses owner/grant restrictions by design but **not** tenant, classification, purpose or time. Working memory is not grant-shareable. Procedural memory needs an approver role and the verified flag.

## Storage and privacy

- New DB files are created mode 0600 and SQLite `secure_delete=ON` with WAL and full synchronous writes; existing production DB files must already have restrictive permissions.
- Scrubbing content from logical tables does not destroy old WAL pages, snapshots, backups, exfiltrated records or external mirrors. Consider encrypted filesystems, encrypted immutable backups, short retention and regular recovery exercises.
- Audit HMAC chaining is optional and must be enabled before first event. Earlier unsealed rows are detectable and not silently rewritten. Store chain head hash outside the database to detect truncation. Changing the HMAC secret invalidates past verification unless an archival key/rotation scheme is designed.
- Hook capture is opt-in and rejects patterns associated with secrets, but cannot guarantee PII removal. Do not enable raw auto-capture for medical, financial or other regulated records without appropriate protections.
- No encryption-at-rest or cross-region deletion coordinator is built into Python code. External key management is required.

## HTTP and denial of service

The API enforces authentication on data operations, read-only health/ready endpoints, a development-only viewer, and aggregate admin metrics. It sets no-store, nosniff, request-id and frame denial headers. `Content-Length` is checked against `FABRIC_MAX_REQUEST_BYTES`; **streaming-body limits, IP throttling, TLS termination, CSP and perimeter WAF belong to the gateway**. Do not expose the local viewer to untrusted networks.

## Prompt injection

`possible_instruction_injection` is heuristic and never authoritative. All recalled content is untrusted evidence. Tool execution must be allowed by an independent, trusted workflow authorization layer—not instructions embedded in a memory.

## Mandatory external controls for production

Network segmentation, TLS/mTLS, secret manager, encryption, ingress rate limiter, identity lifecycle, audit export/SIEM, backup policy, incident response, dependency monitoring, pentesting, and your organizational compliance certification.

## Coordinated vulnerability disclosure

Create a private security advisory or contact the maintainer through the repository's security process. Do not publicly post credentials, tenant data, or exploit instructions with live target details.
