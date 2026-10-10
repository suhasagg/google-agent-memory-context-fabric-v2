# Agent integration guide

## MCP stdio

Install `pip install -e '.[mcp]'`. Start with `fabric connect claude` (or `cursor`, `codex`, `generic`). Copy the generated configuration into the correct client configuration file and replace the database path with an absolute path. Use distinct `FABRIC_AGENT` values for each client. A shared path alone does not grant shared memory: owners must explicitly grant access.

Client examples are in `integrations/agents/`. These are **sample configurations**, not evidence that they were end-to-end tested with every client and released version.

**Security:** MCP stdio runs with local OS rights and consumes `FABRIC_TENANT` / `FABRIC_AGENT` from its trusted environment. It must not be offered as a publicly reachable privileged executable. Remote multi-tenant MCP requires a separately authenticated server with per-request principal propagation.

MCP operations include remember, recall (mode, token budget, graph depth), list, revise, forget, conflicts, neighbors, link, share/revoke, history, profiles, consolidation candidate review and admin-only integrity.

## Google ADK

See [`integrations/google_adk/memory_tools.py`](../integrations/google_adk/memory_tools.py). It binds to a fixed trusted `Principal`; the agent model cannot choose tenant roles. Install the Google ADK package according to its upstream documentation. The adapter source is included but the ADK runtime has not been executed in this environment.

## Opt-in generic agent hooks

Only `prompt`, `user_prompt` or `summary` text is accepted. Tool output, files, full logs, environment variables and internal prompts are not inspected. Set `FABRIC_AUTO_CAPTURE=1` to enable; use `FABRIC_CAPTURE_DRY_RUN=1` for a no-write trial. Include `session_id` and set `FABRIC_PROJECT` per workspace. Identity/session IDs are not stored in raw form. Large or suspicious inputs are discarded.

Example:

```bash
printf '{"prompt":"Use pytest and ruff in CI","session_id":"session-42"}' | \
 FABRIC_AUTO_CAPTURE=1 FABRIC_AGENT=claude-code python -m context_fabric.hooks
```

This is a simple privacy-conscious hook, **not** AgentMemory's complete multi-client native capture pipeline or a validated DLP product.
