# AI Agents in Distill RSS 🤖

## Role

In **Distill RSS**, the AI Agent acts as a **Curator** and **Critic**. It assumes the persona of a Senior Software Engineer specializing in Go (Golang) and Python, with a strong focus on AI Agents, RAG, and Development tools.

## Responsibilities

1. **Relevance Scoring (0-10)**:
   - Evaluates how useful an article is for a Senior Engineer interested in **Neovim (CodeCompanion), AI Agents, RAG, and LLMs**.
   - Filters out generic beginner tutorials unless they cover advanced **CodeCompanion** setups or **Prompt Engineering** techniques.

2. **Summarization**:
   - Provides a one-sentence reason for its relevance (in pt-br).
   - Extracts key takeaways from the provided summary.

3. **Tagging**:
   - Suggests up to 3 relevant tags (e.g., `agent`, `rag`, `codecompanion`).

4. **Daily Digest Generation**:
   - After each run, produces a batch summary with: main themes, novelties, top picks, and an executive paragraph.
   - The digest is stored in `digests.json` and rendered at the top of each day's section in the HTML report.

---

## MCP Tool Integration

Both servers use **stdio transport** (JSON-RPC over stdin/stdout). Each client spawns its own subprocess via `npx`. This means:

- The Distill RSS Python process spawns **its own** context7 and sequential-thinking subprocesses.
- CodeCompanion (Neovim) spawns **its own** independent instances.
- The two sets of processes are completely isolated — stopping ours has zero effect on CodeCompanion's.
- We **never** call stop/shutdown on a process we did not start.

### sequential-thinking

**Server**: `@modelcontextprotocol/server-sequential-thinking`
**Used for**: Batch digest generation (one session per `--analyze` run).

**Protocol** — 4 structured thoughts recorded before Gemini generates the digest JSON:
1. **Theme extraction**: scan the batch for dominant topics.
2. **Novelty detection**: identify new releases, model updates, emerging patterns.
3. **Top picks**: select highest-scoring + broadest-relevance articles.
4. **Executive summary**: draft the pt-br paragraph for the Senior Engineer persona.

The thought log is appended to the Gemini prompt as context, improving digest coherence.

### context7

**Server**: `@upstash/context7-mcp@latest`
**Used for**: Per-article library grounding (called inside `analyze_article_with_ai`).

**Flow**:
1. Scan article title + summary for known library names (`TRACKABLE_LIBRARIES`).
2. Call `resolve-library-id` → get the canonical context7 library ID.
3. Call `get-library-docs` (topic: `overview`, tokens: `800`) → fetch current docs snippet.
4. Inject the snippet into the Gemini analysis prompt to ground scoring against real, up-to-date documentation.

**Why this matters**: Gemini's training data can be stale. context7 ensures that when an article mentions LangGraph 0.3 or a new Gemini model, the scorer has access to the actual current API surface before deciding relevance.

---

## Prompt Strategy

The agent receives a structured prompt containing:
- **Persona**: Senior Software Engineer (Go/Python/AI).
- **Context**: Keywords of interest (from `config.json`).
- **Focus**: **Neovim (CodeCompanion)**, **Prompt Engineering**, **MCP**, **LLMs (Copilot, Gemini, Claude, Deepseek)**, **Python**, **Golang**, **AI Agents**, **RAG**, **Knowledge Bases**.
- **Input**: Article Title, Source, and Truncated Summary (max 500 chars).
- **Protocol**: Sequential-thinking steps are explicit in the prompt body.

### Optimization Techniques

- **Hard Filtering (Pre-AI)**: Articles are only sent to the agent if they match relevant keywords locally.
- **Input Truncation**: Summaries limited to 500 characters to reduce token usage.
- **Structured Output**: The agent returns pure JSON (`response_mime_type="application/json"`).
- **Score Threshold**: Articles scoring < 4 are discarded before being added to history.

---

## Daily Digest (Batch Summary)

After each analysis run, a second AI call aggregates the processed batch:

1. **Theme Extraction** (sequential-thinking Step 1): 3–5 dominant themes across today's articles.
2. **Novelty Detection** (sequential-thinking Step 2): New model releases, framework updates, emerging patterns.
3. **Top Picks** (sequential-thinking Step 3): 3–5 must-read articles by score + relevance.
4. **Executive Summary** (sequential-thinking Step 4): A single paragraph in pt-br.

Results are stored in `digests.json` keyed by `YYYY-MM-DD` and rendered in the HTML report.

---

## HTML Report Pagination by Execution Day

The `rss_report.html` is organized into **day sections**, one per execution run:

- **Navigation bar** (sticky header): links to each day with article count badges.
- **Day section**: shows the digest box (if available) followed by the articles table.
- **Articles sorted by score** (descending) within each day.
- **`run_date` field**: each article carries the date of the run that fetched it; older articles without `run_date` fall back to `analyzed_at` or `published`.

---

## Model Configuration

- **Default Model**: `gemini-2.0-flash` (balanced for speed/cost).
- **Environment Variable**: `GEMINI_MODEL` overrides the model name.
- **Future**: `CLAUDE_MODEL` support planned for migration to Anthropic + MCP native tooling.

---

## Data Files

| File | Purpose |
|------|---------|
| `history.json` | All processed articles (flat list, sorted by score) |
| `digests.json` | Daily batch summaries keyed by `YYYY-MM-DD` |
| `rss_report.html` | Generated HTML report, paginated by day |
| `config.json` | Feed URLs and keyword list |

---

## Development Workflow

**Always run unit tests before considering any code change complete:**

```bash
uv run pytest
```

- All tests must pass before committing.
- If you add or modify behavior, update or add the corresponding test in `tests/`.
