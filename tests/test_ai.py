import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from distill_rss.ai import GeminiArticleAnalyzer, GeminiDigestGenerator
from distill_rss.models import Article, Digest
from distill_rss.mcp_tools import NullContextProvider, NullThinkingRecorder


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

    def test_build_analysis_prompt_injects_context(self):
        article = _make_article()
        prompt = GeminiArticleAnalyzer._build_analysis_prompt(article, ["rag"], context="[ctx7-snippet]")
        assert "context7" in prompt
        assert "[ctx7-snippet]" in prompt

    def test_build_analysis_prompt_omits_context_block_when_empty(self):
        article = _make_article()
        prompt = GeminiArticleAnalyzer._build_analysis_prompt(article, ["rag"])
        assert "context7" not in prompt


# ── GeminiDigestGenerator ──────────────────────────────────────────────────────

class TestGeminiDigestGenerator:
    def _make_generator(self, client) -> GeminiDigestGenerator:
        return GeminiDigestGenerator(client, "gemini-2.0-flash", NullThinkingRecorder())

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

    def test_build_digest_prompt_includes_article_entries(self):
        articles = _scored_articles([8, 6])
        prompt = GeminiDigestGenerator._build_digest_prompt(articles, ["thought 1"])
        assert "Article 0" in prompt
        assert "Article 1" in prompt

    def test_build_digest_prompt_requests_brief_field(self):
        articles = _scored_articles([8])
        prompt = GeminiDigestGenerator._build_digest_prompt(articles, [])
        assert '"brief"' in prompt

    def test_build_thoughts_generates_four_steps(self):
        articles = _scored_articles([8])
        thoughts = GeminiDigestGenerator._build_thoughts(articles, ["rag", "python"])
        assert len(thoughts) == 4
        assert all(isinstance(t, str) for t in thoughts)
