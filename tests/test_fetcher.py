from unittest.mock import MagicMock, patch

import pytest
import requests

from distill_rss.fetcher import FeedFetcher, clean_html
from distill_rss.models import FeedConfig


class TestCleanHtml:
    def test_strips_html_tags(self):
        assert clean_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_returns_plain_text_unchanged(self):
        assert clean_html("plain text") == "plain text"

    def test_handles_empty_string(self):
        assert clean_html("") == ""

    def test_strips_nested_tags(self):
        result = clean_html("<div><span><a href='#'>Link</a></span></div>")
        assert result == "Link"


class TestFeedFetcher:
    @pytest.fixture
    def fetcher(self) -> FeedFetcher:
        return FeedFetcher(max_per_feed=5)

    @pytest.fixture
    def feed(self) -> FeedConfig:
        return FeedConfig(name="Test Blog", url="http://example.com/rss")

    def _make_response(self, status_code: int = 200, content: bytes = b"<rss/>") -> MagicMock:
        response = MagicMock()
        response.status_code = status_code
        response.content = content
        return response

    def _make_entry(
        self,
        title: str = "Title",
        link: str = "http://x.com",
        summary: str = "Summary",
        published: str = "2024-01-01",
    ) -> MagicMock:
        entry = MagicMock()
        entry.title = title
        entry.link = link
        entry.summary = summary
        entry.get = lambda k, default="": {"summary": summary, "published": published}.get(k, default)
        return entry

    def _make_parsed_feed(self, entries: list, bozo: bool = False) -> MagicMock:
        feed = MagicMock()
        feed.bozo = bozo
        feed.bozo_exception = Exception("parse warning") if bozo else None
        feed.entries = entries
        return feed

    def test_respects_max_per_feed_limit(self, fetcher, feed):
        entries = [self._make_entry(title=f"Article {i}") for i in range(10)]
        with (
            patch.object(fetcher, "_get", return_value=self._make_response()),
            patch("distill_rss.fetcher.feedparser.parse", return_value=self._make_parsed_feed(entries)),
        ):
            articles = fetcher._fetch_feed(feed)

        assert len(articles) == 5

    def test_returns_empty_list_on_http_error(self, fetcher, feed):
        with patch.object(fetcher, "_get", return_value=self._make_response(status_code=404)):
            articles = fetcher._fetch_feed(feed)

        assert articles == []

    def test_retries_without_ssl_verification_on_ssl_error(self, fetcher, feed):
        entries = [self._make_entry()]
        with (
            patch.object(fetcher, "_get", side_effect=requests.exceptions.SSLError),
            patch("requests.get", return_value=self._make_response()),
            patch("distill_rss.fetcher.feedparser.parse", return_value=self._make_parsed_feed(entries)),
        ):
            articles = fetcher._fetch_feed(feed)

        assert len(articles) == 1

    def test_maps_entry_fields_to_article(self, fetcher, feed):
        entry = self._make_entry(title="My Post", link="http://blog.com/post", summary="<p>Summary</p>")
        with (
            patch.object(fetcher, "_get", return_value=self._make_response()),
            patch("distill_rss.fetcher.feedparser.parse", return_value=self._make_parsed_feed([entry])),
        ):
            articles = fetcher._fetch_feed(feed)

        assert len(articles) == 1
        assert articles[0].title == "My Post"
        assert articles[0].link == "http://blog.com/post"
        assert articles[0].summary == "Summary"  # HTML stripped
        assert articles[0].source == "Test Blog"

    def test_fetch_aggregates_articles_from_multiple_feeds(self, fetcher):
        feeds = [
            FeedConfig(name="Feed A", url="http://a.com/rss"),
            FeedConfig(name="Feed B", url="http://b.com/rss"),
        ]
        entry = self._make_entry()
        with (
            patch.object(fetcher, "_get", return_value=self._make_response()),
            patch("distill_rss.fetcher.feedparser.parse", return_value=self._make_parsed_feed([entry])),
        ):
            articles = fetcher.fetch(feeds)

        assert len(articles) == 2

    def test_fetch_continues_after_feed_error(self, fetcher):
        feeds = [
            FeedConfig(name="Bad", url="http://bad.com/rss"),
            FeedConfig(name="Good", url="http://good.com/rss"),
        ]
        entry = self._make_entry()
        responses = [
            self._make_response(status_code=500),
            self._make_response(status_code=200),
        ]
        with (
            patch.object(fetcher, "_get", side_effect=responses),
            patch("distill_rss.fetcher.feedparser.parse", return_value=self._make_parsed_feed([entry])),
        ):
            articles = fetcher.fetch(feeds)

        # Only the good feed returns articles
        assert len(articles) == 1
        assert articles[0].source == "Good"
