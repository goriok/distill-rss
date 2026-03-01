"""
Feed fetching — Single Responsibility: fetch and parse RSS entries only.

Console/UI output is left to the caller; this module uses the standard
logging module so it stays decoupled from any Rich console instance.
"""

import logging
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup

from .constants import DEFAULT_MAX_PER_FEED
from .models import Article, FeedConfig

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}


def clean_html(html_content: str) -> str:
    return BeautifulSoup(html_content, "html.parser").get_text()


class FeedFetcher:
    """Fetches and parses RSS feeds, returning a flat list of Articles."""

    def __init__(self, max_per_feed: int = DEFAULT_MAX_PER_FEED):
        self.max_per_feed = max_per_feed

    def fetch(self, feeds: list[FeedConfig]) -> list[Article]:
        articles: list[Article] = []
        for feed in feeds:
            try:
                articles.extend(self._fetch_feed(feed))
            except Exception as exc:
                logger.error("Unexpected error fetching %s: %s", feed.name, exc)
        return articles

    def _fetch_feed(self, feed: FeedConfig) -> list[Article]:
        try:
            response = self._get(feed.url)
        except requests.exceptions.SSLError:
            logger.warning("SSL error for %s — retrying without verification", feed.name)
            response = requests.get(feed.url, headers=_HEADERS, timeout=10, verify=False)

        if response.status_code != 200:
            logger.error("HTTP %d for %s", response.status_code, feed.name)
            return []

        parsed = feedparser.parse(response.content)
        if parsed.bozo:
            logger.warning("Feed parse warning for %s: %s", feed.name, parsed.bozo_exception)

        return [
            Article(
                title=entry.title,
                link=entry.link,
                summary=clean_html(entry.get("summary", entry.get("description", ""))),
                source=feed.name,
                published=entry.get("published", datetime.now().isoformat()),
            )
            for entry in parsed.entries[: self.max_per_feed]
        ]

    def _get(self, url: str) -> requests.Response:
        return requests.get(url, headers=_HEADERS, timeout=10)
