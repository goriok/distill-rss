# Distill RSS 📡

**Distill RSS** is an intelligent RSS reader designed for developers who want to filter signal from noise. It uses Google's Gemini AI to analyze article summaries and determine their relevance to your specific interests (e.g., Go, Python, Software Architecture).

## Features

- **Smart Filtering**: Uses Gemini AI to score and summarize articles based on your keywords.
- **Clean Interface**: Displays a summary table in the terminal using `rich`.
- **HTML Reports**: Generates a detailed HTML report with links to the original articles.
- **Configurable**: Easy to customize feeds and keywords via `config.json`.
- **Efficient**: Implements local keyword pre-filtering and summary truncation to save on AI tokens.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)
- A Google Gemini API Key

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/distill-rss.git
    cd distill-rss
    ```

2.  Install dependencies:
    ```bash
    uv sync
    ```

3.  Set up environment variables:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and add your `GEMINI_API_KEY`. You can also configure the model via `GEMINI_MODEL` (default: `gemini-1.5-flash`).

## Usage

Run the reader with AI analysis enabled:

```bash
uv run rss_reader.py --analyze
```

This will:
1.  Fetch articles from configured feeds.
2.  Filter them based on keywords.
3.  Analyze relevant articles with AI.
4.  Display a table in the terminal.
5.  Generate and open an HTML report (`rss_report.html`).

## Configuration

Edit `config.json` to manage your feeds and keywords of interest:

```json
{
  "feeds": [
    { "name": "My Feed", "url": "https://example.com/rss" }
  ],
  "keywords": ["python", "golang", "ai"]
}
```

## License

MIT
