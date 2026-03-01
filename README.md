# Distill RSS 📡

**Distill RSS** is an intelligent RSS reader designed for developers who want to filter signal from noise. It uses Google Gemini AI — following a **sequential-thinking** protocol — to analyze article summaries, score their relevance, and generate a daily digest of novelties.

## Features

- **Sequential-Thinking Analysis**: Each article is evaluated through a structured 4-step protocol (topic identification → persona assessment → context freshness check → scoring) for consistent, high-quality curation.
- **Daily Digest**: After each run the AI generates a batch summary with main themes, novelties, top picks, and an executive paragraph — all stored in `digests.json`.
- **Day-Paginated HTML Report**: `rss_report.html` groups articles by execution date with a sticky nav bar, digest box, and per-day article tables sorted by relevance score.
- **Smart Filtering**: Local keyword pre-filtering before any AI call; score threshold (≥ 4) before adding to history.
- **Clean Terminal Interface**: Rich-powered table showing the top 20 articles from history.
- **Configurable**: Manage feeds and keywords via `config.json`.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- A Google Gemini API Key

## Installation

```bash
git clone https://github.com/yourusername/distill-rss.git
cd distill-rss
uv sync
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

## Usage

**Fetch feeds + AI analysis + HTML report:**
```bash
uv run rss_reader.py --analyze
```

**Fetch feeds only (no AI, no scoring):**
```bash
uv run rss_reader.py
```

Each `--analyze` run:
1. Fetches articles from all configured feeds.
2. Skips articles already in `history.json`.
3. Pre-filters by keywords locally.
4. Sends remaining articles through the sequential-thinking AI pipeline.
5. Discards articles scoring < 4.
6. Generates a daily digest (main themes, novelties, top picks).
7. Saves results to `history.json` and `digests.json`.
8. Generates and opens `rss_report.html` paginated by run date.

## Configuration

```json
{
  "feeds": [
    { "name": "My Feed", "url": "https://example.com/rss" }
  ],
  "keywords": ["golang", "python", "agent", "mcp", "rag", "nvim"]
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Required. Your Google Gemini API key. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Override the Gemini model name. |

## Data Files

| File | Description |
|------|-------------|
| `history.json` | All analyzed articles, sorted by score. |
| `digests.json` | Daily batch summaries keyed by `YYYY-MM-DD`. |
| `rss_report.html` | Generated report, paginated by execution day. |

## Agent Architecture

See [AGENTS.md](AGENTS.md) for details on the AI agent's role, the sequential-thinking protocol, MCP tool directives (sequential-thinking, context7), and the daily digest pipeline.

## License

MIT
