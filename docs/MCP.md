# MCP Integration

Both servers use **stdio transport** (JSON-RPC over stdin/stdout), spawned via `npx`.

## context7 (`@upstash/context7-mcp@latest`)

Per-article library grounding, called inside `analyze_article_with_ai`.

1. Scan article title + summary for library names in `TRACKABLE_LIBRARIES`
2. `resolve-library-id` → canonical context7 library ID
3. `get-library-docs` (topic: `overview`, tokens: `800`) → current docs snippet
4. Inject snippet into Gemini prompt to ground scoring against up-to-date API surface

## sequential-thinking (`@modelcontextprotocol/server-sequential-thinking`)

One session per `--analyze` run, used for digest generation.

4 structured thoughts recorded before Gemini generates the digest JSON:
1. **Theme extraction** — dominant topics across the batch
2. **Novelty detection** — new releases, model updates, emerging patterns
3. **Top picks** — highest-scoring + broadest-relevance articles
4. **Executive summary** — pt-br paragraph for the Senior Engineer persona

The thought log is appended to the Gemini digest prompt as context.

## Process Isolation

- Distill RSS spawns **its own** context7 and sequential-thinking subprocesses.
- CodeCompanion (Neovim) has **its own** completely independent instances.
- **Never** call stop/shutdown on a process this app did not start.
