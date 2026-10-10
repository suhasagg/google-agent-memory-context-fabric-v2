# Contributing

Thank you for helping build safer agent memory infrastructure.

1. Start from Python >=3.11: `pip install -e '.[dev]'`.
2. Add tests for every behavior or bug fix; run `python -m pytest -q`.
3. Retrieval work requires reporting mode, corpus revision and Recall@K/MRR; include `fabric-evaluate` output.
4. Identity, grants, classifications, forgetting, profile access and OIDC changes require negative security tests. Never trust caller-provided tenant/agent/role fields.
5. Document all external services and **do not mark sample adapters as tested until end-to-end validated**.
6. Do not add secret values or real customer data in issues, test fixtures, output or benchmark corpora.
7. Run packaging validation: `python -m pip wheel --no-deps --wheel-dir dist .`.

Feature requests should state a user problem, intended threat model, deployment assumptions and measurable acceptance tests. The project welcomes external review of its multi-tenant model and backup/forgetting semantics.
