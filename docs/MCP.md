# MCP Integration

Uses **stdio transport** (JSON-RPC over stdin/stdout), spawned via `npx`.

## context7 (`@upstash/context7-mcp@latest`)

Per-article library grounding, called inside `analyze_article_with_ai`.

1. Scan article title + summary for library names in `TRACKABLE_LIBRARIES`
2. `resolve-library-id` → canonical context7 library ID
3. `get-library-docs` (topic: `overview`, tokens: `800`) → current docs snippet
4. Inject snippet into Gemini prompt to ground scoring against up-to-date API surface

## Process Isolation

- Distill RSS spawns **its own** context7 subprocess.
- CodeCompanion (Neovim) has **its own** completely independent instances.
- **Never** call stop/shutdown on a process this app did not start.
