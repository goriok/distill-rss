"""
AI analysis layer — Dependency Inversion in practice.

GeminiArticleAnalyzer depends on:
- LibraryContextProvider (Protocol) — not the concrete Context7Client

This allows unit tests to inject Null Objects and avoids tight coupling to
external services. Callers inject the real implementations at runtime.
"""

import json
import logging
from typing import Protocol

from google import genai
from google.genai import types

from .constants import MAX_DIGEST_ARTICLES, SUMMARY_TRUNCATE
from .models import Article, Digest
from .mcp_tools import (
    LibraryContextProvider,
    NullContextProvider,
)

logger = logging.getLogger(__name__)


# ── Protocols ─────────────────────────────────────────────────────────────────

class ArticleAnalyzer(Protocol):
    async def analyze(self, article: Article, keywords: list[str]) -> dict: ...


class DigestGenerator(Protocol):
    async def generate(self, articles: list[Article], keywords: list[str]) -> Digest | None: ...


# ── Gemini implementations ────────────────────────────────────────────────────

class GeminiArticleAnalyzer:
    """
    Scores and summarizes a single article.

    Pipeline:
      1. Local keyword pre-filter (free — skips AI call for irrelevant articles).
      2. Library context enrichment via context7 (optional, injected).
      3. Gemini call → structured JSON { score, reason, tags }.
    """

    def __init__(
        self,
        client: genai.Client,
        model: str,
        context_provider: LibraryContextProvider | None = None,
    ):
        self._client = client
        self._model = model
        self._context_provider: LibraryContextProvider = context_provider or NullContextProvider()

    async def analyze(self, article: Article, keywords: list[str]) -> dict:
        if not self._matches_keywords(article, keywords):
            return {"score": 0, "reason": "Filtrado localmente (sem palavras-chave)", "tags": []}

        library_context = await self._context_provider.get_context(
            f"{article.title} {article.summary}"
        )
        prompt = self._build_analysis_prompt(article, keywords, library_context)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)
        except Exception as exc:
            logger.warning("Article analysis failed for '%s': %s", article.title, exc)
            return {"score": 0, "reason": "Analysis failed", "tags": []}

    @staticmethod
    def _build_analysis_prompt(
        article: Article,
        keywords: list[str],
        context: str = "",
    ) -> str:
        ctx_block = (
            f"\n\nContext from context7 (current docs):\n{context}" if context else ""
        )
        return (
            "You are a curator for a Senior Software Engineer (Go/Python, AI Agents, Neovim/CodeCompanion).\n\n"
            "Analyze the article below and respond with ONLY valid JSON.\n\n"
            f"Keywords of interest: {', '.join(keywords)}"
            f"{ctx_block}\n\n"
            f"Article title: {article.title}\n"
            f"Article source: {article.source}\n"
            f"Article summary (truncated): {article.summary[:SUMMARY_TRUNCATE]}\n\n"
            "Score (0-10), one-sentence reason (pt-br), up to 3 tags.\n\n"
            '{"score": <int>, "reason": "<string>", "tags": ["<t1>", "<t2>"]}'
        )

    @staticmethod
    def _matches_keywords(article: Article, keywords: list[str]) -> bool:
        text = f"{article.title} {article.summary}".lower()
        return any(k.lower() in text for k in keywords)


class GeminiDigestGenerator:
    """
    Produces a daily digest from the batch of accepted articles.

    Pipeline:
      1. Gemini call → Digest { brief, main_themes, novelties, top_picks, summary }.
    """

    def __init__(self, client: genai.Client, model: str):
        self._client = client
        self._model = model

    async def generate(self, articles: list[Article], keywords: list[str]) -> Digest | None:
        if not articles:
            return None

        top = sorted(articles, key=lambda a: a.score, reverse=True)[:MAX_DIGEST_ARTICLES]
        prompt = self._build_digest_prompt(top)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return Digest.from_dict(json.loads(response.text))
        except Exception as exc:
            logger.warning("Batch digest generation failed: %s", exc)
            return None

    @staticmethod
    def _build_digest_prompt(top: list[Article]) -> str:
        article_lines = "\n".join(
            f"- [{a.score}/10] {a.title} ({a.source}): {a.reason or a.summary[:80]}"
            for a in top
        )
        return (
            "You are a Senior Software Engineer curator. Summarize today's RSS batch.\n\n"
            f"Articles (sorted by relevance score):\n{article_lines}\n\n"
            "Output ONLY valid JSON:\n"
            "{\n"
            '  "brief": "<1-2 sentences in pt-br listing the main topics covered today>",\n'
            '  "main_themes": ["<theme>"],\n'
            '  "novelties": ["<novelty>"],\n'
            '  "top_picks": [{"title": "<t>", "reason": "<r>"}],\n'
            '  "summary": "<paragraph in pt-br>"\n'
            "}"
        )
