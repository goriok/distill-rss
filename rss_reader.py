import argparse
import json
import os
from datetime import datetime

import feedparser
import requests
import urllib3
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types
import webbrowser
from rich.console import Console

from rich.markdown import Markdown
from rich.table import Table

load_dotenv()

# Initialize Rich Console
console = Console()

# Disable SSL Warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config(config_path="config.json"):
    with open(config_path, "r") as f:
        return json.load(f)


def clean_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text()


def fetch_feeds(config):
    articles = []
    feeds = config.get("feeds", [])

    # Headers to mimic a browser and avoid some basic bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    }

    with console.status("[bold green]Fetching RSS feeds...") as status:
        for feed_info in feeds:
            feed_url = feed_info["url"]
            feed_name = feed_info["name"]

            try:
                # Use requests to get content first, allows custom headers/cookies
                try:
                    response = requests.get(feed_url, headers=headers, timeout=10)

                except requests.exceptions.SSLError:
                    console.print(
                        f"[yellow]SSL Error for {feed_name}, trying without verification...[/yellow]"
                    )
                    response = requests.get(
                        feed_url, headers=headers, timeout=10, verify=False
                    )

                if response.status_code != 200:
                    console.print(
                        f"[red]Error fetching {feed_name}: HTTP {response.status_code}[/red]"
                    )
                    continue

                # Parse the raw XML content
                feed = feedparser.parse(response.content)

                if feed.bozo:
                    console.print(
                        f"[yellow]Warning parsing feed {feed_name}: {feed.bozo_exception}[/yellow]"
                    )
                    # Continue anyway as feedparser often parses despite minor errors

                for entry in feed.entries[:5]:  # Limit to 5 per feed for now
                    # Basic extraction
                    article = {
                        "title": entry.title,
                        "link": entry.link,
                        "summary": clean_html(
                            entry.get("summary", entry.get("description", ""))
                        ),
                        "source": feed_name,
                        "published": entry.get("published", datetime.now().isoformat()),
                    }
                    articles.append(article)
            except Exception as e:
                console.print(f"[red]Error fetching {feed_name}: {str(e)}[/red]")

    return articles


def generate_html_report(articles):

    """
    Generates a simple HTML report with the results.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RSS Reader Report</title>
        <style>
            body { font-family: sans-serif; margin: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .score { font-weight: bold; text-align: center; }
            .high-score { color: green; }
            .medium-score { color: orange; }
            .low-score { color: red; }
            a { text-decoration: none; color: #007bff; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>Latest News Analysis</h1>
        <table>
            <thead>
                <tr>
                    <th>Score</th>
                    <th>Title</th>
                    <th>Source</th>
                    <th>Summary/Reason</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for article in articles:
        # Determine score class
        score_val = 0
        try:
            score_val = int(article.get("score", 0))
        except:
            pass
            
        score_class = "low-score"
        if score_val >= 7:
            score_class = "high-score"
        elif score_val >= 4:
            score_class = "medium-score"

        html_content += f"""
            <tr>
                <td class="score {score_class}">{article.get("score", "-")}</td>
                <td>{article['title']}</td>
                <td>{article['source']}</td>
                <td>{article.get('reason', article['summary'][:200] + '...')}</td>
                <td><a href="{article['link']}" target="_blank">Open</a></td>
            </tr>
        """
        
    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    filename = "rss_report.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return filename




def generate_html_report(articles):
    """
    Generates a simple HTML report with the results.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RSS Reader Report</title>
        <style>
            body { font-family: sans-serif; margin: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .score { font-weight: bold; text-align: center; }
            .high-score { color: green; }
            .medium-score { color: orange; }
            .low-score { color: red; }
            a { text-decoration: none; color: #007bff; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>Latest News Analysis</h1>
        <table>
            <thead>
                <tr>
                    <th>Score</th>
                    <th>Title</th>
                    <th>Source</th>
                    <th>Summary/Reason</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for article in articles:
        # Determine score class
        score_val = 0
        try:
            score_val = int(article.get("score", 0))
        except:
            pass
            
        score_class = "low-score"
        if score_val >= 7:
            score_class = "high-score"
        elif score_val >= 4:
            score_class = "medium-score"

        summary = article.get('reason', article['summary'][:200] + '...')

        html_content += f'''
            <tr>
                <td class="score {score_class}">{article.get("score", "-")}</td>
                <td>{article['title']}</td>
                <td>{article['source']}</td>
                <td>{summary}</td>
                <td><a href="{article['link']}" target="_blank">Open</a></td>
            </tr>
        '''
        
    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    filename = "rss_report.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return filename

def analyze_article_with_ai(client, article, keywords):

    """
    Uses Google Gemini to summarize and score relevance for a Golang/Python developer.
    """
    text_to_check = (article["title"] + " " + article["summary"]).lower()
    basic_keywords = [k.lower() for k in keywords]


    if not any(k in text_to_check for k in basic_keywords):
        return {"score": 0, "reason": "Filtrado localmente (sem palavras-chave)", "tags": []}

    prompt = f"""

    You are an AI assistant for a Senior Software Engineer specializing in Go (Golang) and Python.
    Your task is to analyze the following article summary and determine if it is relevant to their interests.
    
    Keywords of interest: {", ".join(keywords)}
    
    Article Title: {article["title"]}
    Article Source: {article["source"]}
    Article Summary: {article["summary"][:500]}... (truncated)

    
    Please provide:
    1. A relevance score (0-10) based on how useful this is for a Go/Python expert.
    2. A one-sentence summary of why it's relevant (or not).
    3. Suggested tags (max 3).
    
    Format output as JSON:
    {{
        "score": <int>,
        "reason": "<string>",
        "tags": ["<tag1>", "<tag2>"]
    }}
    """

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )



        return json.loads(response.text)

    except Exception as e:
        # console.print(f"[yellow]AI Analysis failed: {e}[/yellow]")
        return {"score": 0, "reason": "Analysis failed", "tags": []}


def main():
    parser = argparse.ArgumentParser(description="AI RSS Reader for Go/Python Devs")
    parser.add_argument(
        "--analyze", action="store_true", help="Use AI to analyze articles"
    )
    args = parser.parse_args()

    config = load_config()
    articles = fetch_feeds(config)

    console.print(
        f"\n[bold]Found {len(articles)} articles from {len(config['feeds'])} feeds.[/bold]\n"
    )

    # AI Analysis Setup
    client = None
    if args.analyze:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            console.print(
                "[red]Error: GEMINI_API_KEY environment variable not set.[/red]"
            )
            return
        client = genai.Client(api_key=api_key)

    # Table output

    processed_articles = []

    table = Table(title="Latest News")
    table.add_column("Score", justify="center", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("Source", style="green")
    table.add_column("Link", style="blue")

    with console.status("[bold blue]Processing articles...") as status:

        for article in articles:
            score = "-"
            reason = article["summary"][:100] + "..."

            if args.analyze:
                if client:
                    analysis = analyze_article_with_ai(
                        client, article, config.get("keywords", [])
                    )

                    score = str(analysis.get("score", 0))
                    reason = analysis.get("reason", "No reason provided")
                    
                    # Store analysis in article for report
                    article["score"] = score
                    article["reason"] = reason

                    # Filter out low relevance if desired, e.g., score < 5
                    if analysis.get("score", 0) < 4:
                        continue
                else:
                    console.print(
                        "[yellow]Skipping AI analysis (Model not initialized)[/yellow]"
                    )
            
            processed_articles.append(article)
            table.add_row(
                score,
                article["title"],
                article["source"],
                article["link"],
            )

    console.print(table)

    # Generate and open HTML report
    if processed_articles:
        report_file = generate_html_report(processed_articles)
        console.print(f"\n[green]Report generated: {report_file}[/green]")
        console.print("[blue]Opening in browser...[/blue]")
        webbrowser.open(f"file://{os.path.abspath(report_file)}")


if __name__ == "__main__":
    main()

