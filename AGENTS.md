# Distill RSS – Agent Guide

## Project

RSS article curator that scores, summarizes, and digests tech articles for a Senior Go/Python/AI
engineer persona. Uses Gemini AI + MCP tools (context7, sequential-thinking).

## Stack & Commands

- Python 3.11+, **uv** (never pip)
- Run: `uv run rss_reader.py --analyze`
- Test: `uv run pytest` — all tests must pass before any change is complete
- Add/modify behavior → add or update the corresponding test in `tests/`

## Critical Constraints

- **Never** call stop/shutdown on MCP subprocesses you did not start. The app spawns its own
  context7 and sequential-thinking processes; CodeCompanion has its own independent instances —
  completely isolated.
- Articles scoring < 4 are discarded before being added to history.

## MCP Integration

Two MCP servers (stdio transport, spawned via `npx`): **context7** for per-article library
grounding and **sequential-thinking** for digest generation.

See `docs/MCP.md` for protocols and flow details.

## Application AI Layer

Gemini agent scores articles 0–10, summarizes in pt-br, and generates daily digests.
Prompt logic lives in `distill_rss/ai.py`. MCP client protocols in `distill_rss/mcp_tools.py`.

## Guardrails

- **Never** delete or overwrite `history.json`, `digests.json`, or `rss_report.html` without
  explicit user confirmation — these are the sole persistent data store.
- **Never** `git push --force` or `git reset --hard` without confirmation.
- **Never** install packages with `pip` — use `uv add` only.
- Before any bulk edit that touches more than 3 files, state the plan and wait for approval.
