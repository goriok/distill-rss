import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from distill_rss.ai import GeminiArticleAnalyzer, GeminiDigestGenerator, _is_retryable, deduplicate_articles
from distill_rss.models import Article, Digest
from distill_rss.mcp_tools import NullContextProvider


# ── Retry test helpers ────────────────────────────────────────────────────────

class _RateLimitError(Exception):
    """Simulates Gemini 429 / ResourceExhausted."""
    code = 429


class _AuthError(Exception):
    """Simulates a permanent auth failure (non-retryable)."""
    code = 401


@pytest.fixture
def no_retry_sleep(monkeypatch):
    """Patch asyncio.sleep so tenacity retries without real delays."""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))


# ── Local helpers (complement conftest fixtures) ───────────────────────────────

def _make_article(title: str = "Building RAG with LangChain", summary: str = "How to use LangChain for RAG pipelines in Python") -> Article:
    return Article(
        title=title,
        link="http://example.com/article",
        summary=summary,
        source="Tech Blog",
        published="2024-01-01",
    )


def _scored_articles(scores: list[int]) -> list[Article]:
    return [
        Article(title=f"Article {i}", link=f"http://{i}.com", summary="Summary",
                source="Blog", published="", score=s)
        for i, s in enumerate(scores)
    ]


def _make_gemini_client(response_text: str) -> MagicMock:
    response = MagicMock()
    response.text = response_text
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


_KEYWORDS = ["rag", "python", "langchain", "agent"]


# ── _is_retryable ─────────────────────────────────────────────────────────────

class TestIsRetryable:
    def test_rate_limit_by_code(self):
        assert _is_retryable(_RateLimitError())

    def test_server_error_by_code(self):
        err = Exception()
        err.code = 500  # type: ignore[attr-defined]
        assert _is_retryable(err)

    def test_retryable_by_class_name(self):
        class ResourceExhausted(Exception): pass
        assert _is_retryable(ResourceExhausted())

    def test_auth_error_is_not_retryable(self):
        assert not _is_retryable(_AuthError())

    def test_generic_exception_is_not_retryable(self):
        assert not _is_retryable(Exception("generic"))


# ── GeminiArticleAnalyzer ──────────────────────────────────────────────────────

class TestGeminiArticleAnalyzer:
    def _make_analyzer(self, client) -> GeminiArticleAnalyzer:
        return GeminiArticleAnalyzer(client, "gemini-2.0-flash", NullContextProvider())

    async def test_irrelevant_article_is_filtered_without_calling_ai(self, irrelevant_article):
        client = MagicMock()
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(irrelevant_article, _KEYWORDS)

        assert result["score"] == 0
        client.aio.models.generate_content.assert_not_called()

    async def test_relevant_article_triggers_ai_call(self):
        payload = json.dumps({"score": 8, "reason": "Muito relevante", "tags": ["rag"]})
        client = _make_gemini_client(payload)
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(_make_article(), _KEYWORDS)

        assert result["score"] == 8
        client.aio.models.generate_content.assert_called_once()

    async def test_returns_fallback_on_api_exception(self):
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(side_effect=Exception("Network error"))
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(_make_article(), _KEYWORDS)

        assert result["score"] == 0
        assert result["reason"] == "Analysis failed"
        assert result["tags"] == []

    async def test_parses_tags_from_response(self):
        payload = json.dumps({"score": 7, "reason": "Relevante", "tags": ["rag", "langchain", "python"]})
        client = _make_gemini_client(payload)
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(_make_article(), _KEYWORDS)

        assert result["tags"] == ["rag", "langchain", "python"]

    async def test_keyword_match_is_case_insensitive(self):
        payload = json.dumps({"score": 6, "reason": "OK", "tags": []})
        client = _make_gemini_client(payload)
        analyzer = self._make_analyzer(client)

        article = _make_article(title="Advanced RAG Techniques")  # uppercase RAG
        result = await analyzer.analyze(article, ["rag"])

        assert result["score"] == 6

    async def test_uses_context_provider_when_injected(self):
        payload = json.dumps({"score": 9, "reason": "Excellent", "tags": ["rag"]})
        client = _make_gemini_client(payload)

        context_provider = MagicMock()
        context_provider.get_context = AsyncMock(return_value="[context7 – langchain docs]: overview...")

        analyzer = GeminiArticleAnalyzer(client, "gemini-2.0-flash", context_provider)
        await analyzer.analyze(_make_article(), _KEYWORDS)

        context_provider.get_context.assert_called_once()
        assert "context7" in str(client.aio.models.generate_content.call_args)

    async def test_retries_on_rate_limit_then_succeeds(self, no_retry_sleep):
        payload = json.dumps({"score": 8, "reason": "Muito relevante", "tags": ["rag"]})
        good_response = MagicMock()
        good_response.text = payload
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            side_effect=[_RateLimitError("rate limit"), good_response]
        )
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(_make_article(), _KEYWORDS)

        assert result["score"] == 8
        assert client.aio.models.generate_content.call_count == 2

    async def test_permanent_error_fails_fast_without_retry(self, no_retry_sleep):
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(side_effect=_AuthError("unauthorized"))
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(_make_article(), _KEYWORDS)

        assert result["score"] == 0
        assert client.aio.models.generate_content.call_count == 1

    async def test_returns_fallback_after_all_retries_exhausted(self, no_retry_sleep):
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(side_effect=_RateLimitError("rate limit"))
        analyzer = self._make_analyzer(client)

        result = await analyzer.analyze(_make_article(), _KEYWORDS)

        assert result["score"] == 0
        assert result["reason"] == "Analysis failed"
        assert client.aio.models.generate_content.call_count == 3  # stop_after_attempt(3)

    def test_build_analysis_prompt_injects_context(self):
        article = _make_article()
        prompt = GeminiArticleAnalyzer._build_analysis_prompt(article, ["rag"], context="[ctx7-snippet]")
        assert "context7" in prompt
        assert "[ctx7-snippet]" in prompt

    def test_build_analysis_prompt_omits_context_block_when_empty(self):
        article = _make_article()
        prompt = GeminiArticleAnalyzer._build_analysis_prompt(article, ["rag"])
        assert "context7" not in prompt

    async def test_logs_analyzed_entry_with_score_and_latency(self, caplog):
        payload = json.dumps({"score": 8, "reason": "Muito relevante", "tags": ["rag"]})
        client = _make_gemini_client(payload)
        analyzer = self._make_analyzer(client)

        with caplog.at_level(logging.INFO, logger="distill_rss.ai"):
            await analyzer.analyze(_make_article(), _KEYWORDS)

        record = next(r for r in caplog.records if r.getMessage() == "article.analyzed")
        assert record.score == 8
        assert record.title == "Building RAG with LangChain"
        assert isinstance(record.latency_ms, float)
        assert record.latency_ms >= 0

    async def test_logs_filtered_entry_for_irrelevant_article(self, caplog, irrelevant_article):
        client = MagicMock()
        analyzer = self._make_analyzer(client)

        with caplog.at_level(logging.INFO, logger="distill_rss.ai"):
            await analyzer.analyze(irrelevant_article, _KEYWORDS)

        record = next(r for r in caplog.records if r.getMessage() == "article.filtered")
        assert record.score == 0
        assert isinstance(record.latency_ms, float)


# ── GeminiDigestGenerator ──────────────────────────────────────────────────────

class TestGeminiDigestGenerator:
    def _make_generator(self, client) -> GeminiDigestGenerator:
        return GeminiDigestGenerator(client, "gemini-2.0-flash")

    async def test_returns_none_for_empty_articles(self, keywords):
        client = MagicMock()
        generator = self._make_generator(client)

        result = await generator.generate([], keywords)

        assert result is None
        client.aio.models.generate_content.assert_not_called()

    async def test_returns_digest_on_success(self, keywords):
        payload = json.dumps({
            "brief": "Hoje: RAG e novidades de AI.",
            "main_themes": ["AI", "RAG"],
            "novelties": ["New LangChain version"],
            "top_picks": [{"title": "Best Article", "reason": "Top score"}],
            "summary": "Resumo do dia em pt-br.",
        })
        client = _make_gemini_client(payload)
        generator = self._make_generator(client)

        result = await generator.generate(_scored_articles([8, 6]), keywords)

        assert isinstance(result, Digest)
        assert result.main_themes == ["AI", "RAG"]
        assert result.summary == "Resumo do dia em pt-br."
        assert result.brief == "Hoje: RAG e novidades de AI."
        assert result.top_picks[0].title == "Best Article"

    async def test_returns_none_on_api_exception(self, keywords):
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))
        generator = self._make_generator(client)

        result = await generator.generate(_scored_articles([8]), keywords)

        assert result is None

    async def test_limits_to_top_25_articles(self, keywords):
        payload = json.dumps({
            "brief": "", "main_themes": [], "novelties": [], "top_picks": [], "summary": ""
        })
        client = _make_gemini_client(payload)
        generator = self._make_generator(client)

        articles = _scored_articles(range(30))
        await generator.generate(articles, keywords)

        prompt = str(client.aio.models.generate_content.call_args)
        # Top scores (scores 5–29) must appear; bottom scores (0–4) must be excluded
        assert "Article 29" in prompt
        assert "Article 5" in prompt
        assert "Article 4" not in prompt  # score 4 is rank 26 — excluded
        assert "Article 0" not in prompt  # score 0 is lowest — excluded

    async def test_retries_on_rate_limit_then_returns_digest(self, keywords, no_retry_sleep):
        payload = json.dumps({
            "brief": "Brief", "main_themes": [], "novelties": [], "top_picks": [], "summary": "S"
        })
        good_response = MagicMock()
        good_response.text = payload
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(
            side_effect=[_RateLimitError("rate limit"), good_response]
        )
        generator = self._make_generator(client)

        result = await generator.generate(_scored_articles([8]), keywords)

        assert isinstance(result, Digest)
        assert client.aio.models.generate_content.call_count == 2

    async def test_permanent_error_returns_none_without_retry(self, keywords, no_retry_sleep):
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(side_effect=_AuthError("unauthorized"))
        generator = self._make_generator(client)

        result = await generator.generate(_scored_articles([8]), keywords)

        assert result is None
        assert client.aio.models.generate_content.call_count == 1

    def test_build_digest_prompt_includes_article_entries(self):
        articles = _scored_articles([8, 6])
        prompt = GeminiDigestGenerator._build_digest_prompt(articles)
        assert "Article 0" in prompt
        assert "Article 1" in prompt

    def test_build_digest_prompt_requests_brief_field(self):
        articles = _scored_articles([8])
        prompt = GeminiDigestGenerator._build_digest_prompt(articles)
        assert '"brief"' in prompt

    async def test_logs_digest_generated_with_count_and_latency(self, keywords, caplog):
        payload = json.dumps({
            "brief": "Hoje: RAG.", "main_themes": [], "novelties": [], "top_picks": [], "summary": "S"
        })
        client = _make_gemini_client(payload)
        generator = self._make_generator(client)

        with caplog.at_level(logging.INFO, logger="distill_rss.ai"):
            await generator.generate(_scored_articles([8, 6]), keywords)

        record = next(r for r in caplog.records if r.getMessage() == "digest.generated")
        assert record.article_count == 2
        assert isinstance(record.latency_ms, float)
        assert record.latency_ms >= 0


# ── deduplicate_articles ───────────────────────────────────────────────────────

def _dup_article(title: str, link: str) -> Article:
    return Article(title=title, link=link, summary="", source="Blog", published="2024-01-01")


class TestDeduplicateArticles:
    def test_empty_list_returns_empty(self):
        assert deduplicate_articles([]) == []

    def test_unique_articles_pass_through_unchanged(self):
        articles = [
            _dup_article("Python RAG Tutorial", "http://a.com/1"),
            _dup_article("Go Concurrency Patterns", "http://b.com/2"),
        ]
        assert deduplicate_articles(articles) == articles

    def test_exact_url_duplicate_removed(self):
        articles = [
            _dup_article("Article One", "http://example.com/article"),
            _dup_article("Article One", "http://example.com/article"),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 1

    def test_url_trailing_slash_normalized(self):
        articles = [
            _dup_article("Article One", "http://example.com/article/"),
            _dup_article("Article One", "http://example.com/article"),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 1

    def test_near_identical_title_removed(self):
        articles = [
            _dup_article("Building RAG Pipelines with LangChain", "http://a.com/1"),
            _dup_article("Building RAG Pipelines with LangChain in Python", "http://b.com/2"),
        ]
        result = deduplicate_articles(articles, threshold=85.0)
        assert len(result) == 1
        assert result[0].link == "http://a.com/1"

    def test_distinct_titles_both_kept(self):
        articles = [
            _dup_article("Python async tutorial", "http://a.com/1"),
            _dup_article("Go concurrency deep dive", "http://b.com/2"),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 2

    def test_first_occurrence_is_kept_on_title_match(self):
        articles = [
            _dup_article("RAG with LangChain", "http://first.com/1"),
            _dup_article("RAG with LangChain", "http://second.com/2"),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 1
        assert result[0].link == "http://first.com/1"

    def test_high_threshold_keeps_similar_articles(self):
        articles = [
            _dup_article("Building RAG with LangChain", "http://a.com/1"),
            _dup_article("Building RAG with LangChain in Python", "http://b.com/2"),
        ]
        result = deduplicate_articles(articles, threshold=99.0)
        assert len(result) == 2

    def test_logs_dedup_removed_count(self, caplog):
        articles = [
            _dup_article("Duplicate Article", "http://a.com/1"),
            _dup_article("Duplicate Article", "http://a.com/1"),
        ]
        with caplog.at_level(logging.INFO, logger="distill_rss.ai"):
            deduplicate_articles(articles)

        record = next(r for r in caplog.records if r.getMessage() == "dedup.removed")
        assert record.dropped == 1
        assert record.remaining == 1

    def test_no_log_when_no_duplicates(self, caplog):
        articles = [
            _dup_article("Python Tutorial", "http://a.com/1"),
            _dup_article("Go Tutorial", "http://b.com/2"),
        ]
        with caplog.at_level(logging.INFO, logger="distill_rss.ai"):
            deduplicate_articles(articles)

        assert not any(r.getMessage() == "dedup.removed" for r in caplog.records)
