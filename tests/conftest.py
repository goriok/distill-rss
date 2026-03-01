"""
Shared pytest fixtures for all test modules.

Centralises test data factories so individual test files stay focused on
behaviour rather than setup boilerplate.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from distill_rss.models import Article, Digest, TopPick


# ── Article factories ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_article() -> Article:
    return Article(
        title="Building RAG with LangChain",
        link="http://example.com/rag-langchain",
        summary="How to use LangChain for RAG pipelines in Python",
        source="Tech Blog",
        published="2024-01-01",
    )


@pytest.fixture
def irrelevant_article() -> Article:
    return Article(
        title="Gardening tips for spring",
        link="http://example.com/garden",
        summary="How to grow tomatoes in your backyard",
        source="Lifestyle",
        published="2024-01-01",
    )


@pytest.fixture
def scored_article() -> Article:
    return Article(
        title="Top RAG Article",
        link="http://example.com/top",
        summary="Advanced RAG techniques with LangChain",
        source="AI Blog",
        published="2024-01-01",
        score=8,
        reason="Muito relevante para engenheiros de AI",
        tags=["rag", "langchain"],
        run_date="2024-01-01",
    )


# ── Digest factory ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_digest() -> Digest:
    return Digest(
        main_themes=["AI", "RAG"],
        novelties=["New LangChain version"],
        top_picks=[TopPick(title="Best Article", reason="Top score")],
        summary="Resumo do dia em pt-br.",
    )


# ── Keyword fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def keywords() -> list[str]:
    return ["rag", "python", "langchain", "agent"]


# ── Gemini client mock factory ─────────────────────────────────────────────────

@pytest.fixture
def make_gemini_client():
    """Returns a factory that creates a mock Gemini client with a fixed JSON response."""

    def _factory(response_payload: dict) -> MagicMock:
        response = MagicMock()
        response.text = json.dumps(response_payload)
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(return_value=response)
        return client

    return _factory
