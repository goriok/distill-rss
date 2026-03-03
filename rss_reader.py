"""
Distill RSS – CLI entry point.

This module is intentionally thin: it wires together the components from
distill_rss/, handles CLI parsing, manages the MCP subprocess lifecycle,
and delegates everything else to the appropriate class.

No business logic lives here — only orchestration and dependency injection.
"""

import argparse
import asyncio
import os
import webbrowser
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.table import Table

from distill_rss.ai import GeminiArticleAnalyzer, GeminiDigestGenerator, deduplicate_articles
from distill_rss.constants import DEFAULT_GEMINI_MODEL, MIN_ACCEPTED_SCORE
from distill_rss.fetcher import FeedFetcher
from distill_rss.mcp_tools import Context7Client
from distill_rss.models import Article, Digest
from distill_rss.persistence import ConfigLoader, JsonArticleRepository, JsonDigestRepository
from distill_rss.report import HTMLReportGenerator

load_dotenv()

console = Console()

MCP_CONTEXT7 = StdioServerParameters(
    command="npx",
    args=["-y", "@upstash/context7-mcp@latest"],
)


_ANALYZE_CONCURRENCY = 8  # max parallel Gemini calls; tune down if rate-limited


async def _analyze_articles(
    analyzer: GeminiArticleAnalyzer,
    articles: list[Article],
    history_links: set[str],
    keywords: list[str],
    run_date: str,
) -> list[Article]:
    """Run AI analysis over new articles concurrently, returning only accepted ones (score >= threshold)."""
    semaphore = asyncio.Semaphore(_ANALYZE_CONCURRENCY)

    async def _process(article: Article) -> Article | None:
        if article.link in history_links:
            return None
        async with semaphore:
            article.run_date = run_date
            result = await analyzer.analyze(article, keywords)
        article.score = int(result.get("score", 0))
        article.reason = result.get("reason", "")
        article.tags = result.get("tags", [])
        article.analyzed_at = datetime.now().isoformat()
        return article if article.score >= MIN_ACCEPTED_SCORE else None

    results = await asyncio.gather(*(_process(a) for a in articles))
    return [a for a in results if a is not None]


def _display_digest_summary(digest: Digest, run_date: str) -> None:
    """Print digest summary to the console."""
    console.print(f"[green]Digest saved for {run_date}[/green]")
    console.print(f"\n[bold cyan]== Digest {run_date} ==[/bold cyan]")
    console.print(f"[bold]Temas:[/bold] {', '.join(digest.main_themes)}")
    for novelty in digest.novelties:
        console.print(f"  • {novelty}")
    console.print(f"\n[bold]Resumo:[/bold] {digest.summary}\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Distill RSS – AI-powered feed reader")
    parser.add_argument("--analyze", action="store_true", help="Use AI to analyze articles")
    args = parser.parse_args()

    config = ConfigLoader().load()
    article_repo = JsonArticleRepository()
    digest_repo = JsonDigestRepository()
    reporter = HTMLReportGenerator()

    articles = deduplicate_articles(FeedFetcher().fetch(config.feeds))
    history = article_repo.load()
    digests = digest_repo.load()

    console.print(f"\n[bold]Found {len(articles)} articles from {len(config.feeds)} feeds.[/bold]")
    console.print(f"[bold]Loaded {len(history)} articles from history.[/bold]\n")

    if not args.analyze:
        _print_table(history[:20], "Top News (History)")
        report_path = reporter.generate(history, digests)
        console.print(f"\n[green]Report: {report_path}[/green]")
        webbrowser.open(f"file://{report_path.absolute()}")
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error: GEMINI_API_KEY not set.[/red]")
        return

    gemini_client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    run_date = datetime.now().strftime("%Y-%m-%d")
    history_links = {a.link for a in history}

    # We own the context7 MCP subprocess below.
    # It is completely independent from any CodeCompanion-spawned instances.
    async with stdio_client(MCP_CONTEXT7) as (ctx7_r, ctx7_w):
        async with ClientSession(ctx7_r, ctx7_w) as ctx7:
            await ctx7.initialize()
            console.print("[dim]MCP context7 ready[/dim]\n")

            analyzer = GeminiArticleAnalyzer(
                gemini_client, model_name, Context7Client(ctx7)
            )
            digest_gen = GeminiDigestGenerator(gemini_client, model_name)

            with console.status("[bold blue]Analyzing articles..."):
                new_articles = await _analyze_articles(
                    analyzer, articles, history_links, config.keywords, run_date
                )

            if new_articles:
                console.print("\n[bold blue]Generating daily digest...[/bold blue]")
                digest = await digest_gen.generate(new_articles, config.keywords)
                if digest:
                    digests[run_date] = digest
                    digest_repo.save(digests)
                    _display_digest_summary(digest, run_date)

    history.extend(new_articles)
    history.sort(key=lambda a: a.score, reverse=True)
    article_repo.save(history)

    _print_table(history[:20], "Top News (History + New)")
    report_path = reporter.generate(history, digests)
    console.print(f"\n[green]Report: {report_path}[/green]")
    webbrowser.open(f"file://{report_path.absolute()}")


def _print_table(articles: list[Article], title: str) -> None:
    table = Table(title=title)
    table.add_column("Score", justify="center", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("Source", style="green")
    table.add_column("Date", style="yellow")
    for a in articles:
        table.add_row(str(a.score), a.title[:80], a.source, a.effective_date)
    console.print(table)


if __name__ == "__main__":
    asyncio.run(main())
