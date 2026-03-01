"""
AI analysis layer — Dependency Inversion in practice.

GeminiArticleAnalyzer and GeminiDigestGenerator depend on:
- LibraryContextProvider (Protocol) — not the concrete Context7Client
- ThinkingRecorder (Protocol) — not the concrete SequentialThinkingClient

This allows unit tests to inject Null Objects and avoids tight coupling to
external services. Callers inject the real implementations at runtime.
"""

import json
import logging
from typing import Protocol

from google import genai
from google.genai import types

from .constants import MAX_ANALYSIS_OUTPUT_TOKENS, MAX_DIGEST_ARTICLES, MAX_DIGEST_OUTPUT_TOKENS, SUMMARY_TRUNCATE
from .models import Article, Digest
from .mcp_tools import (
    LibraryContextProvider,
    NullContextProvider,
    NullThinkingRecorder,
    ThinkingRecorder,
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
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=MAX_ANALYSIS_OUTPUT_TOKENS,
                ),
            )
            meta = response.usage_metadata
            logger.info(
                "tokens used (analysis) — prompt=%s output=%s total=%s",
                meta.prompt_token_count,
                meta.candidates_token_count,
                meta.total_token_count,
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
      1. sequential-thinking: records 4 structured reasoning steps (optional, injected).
      2. Gemini call → Digest { main_themes, novelties, top_picks, summary }.
    """

    def __init__(
        self,
        client: genai.Client,
        model: str,
        thinking_recorder: ThinkingRecorder | None = None,
    ):
        self._client = client
        self._model = model
        self._thinking_recorder: ThinkingRecorder = thinking_recorder or NullThinkingRecorder()

    async def generate(self, articles: list[Article], keywords: list[str]) -> Digest | None:
        if not articles:
            return None

        top = sorted(articles, key=lambda a: a.score, reverse=True)[:MAX_DIGEST_ARTICLES]
        thoughts = self._build_thoughts(top, keywords)
        thought_log = await self._thinking_recorder.record(thoughts)
        prompt = self._build_digest_prompt(top, thought_log)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=MAX_DIGEST_OUTPUT_TOKENS,
                ),
            )
            meta = response.usage_metadata
            logger.info(
                "tokens used (digest) — prompt=%s output=%s total=%s",
                meta.prompt_token_count,
                meta.candidates_token_count,
                meta.total_token_count,
            )
            return Digest.from_dict(json.loads(response.text))
        except Exception as exc:
            logger.warning("Batch digest generation failed: %s", exc)
            return None

    @staticmethod
    def _build_thoughts(top: list[Article], keywords: list[str]) -> list[str]:
        return [
            f"Step 1 – Theme extraction: scanning {len(top)} articles for dominant topics "
            f"related to {', '.join(keywords[:6])}.",
            "Step 2 – Novelty detection: identifying new releases, model updates, and emerging patterns.",
            "Step 3 – Top picks: selecting the 3-5 highest-scoring articles with the broadest relevance.",
            "Step 4 – Executive summary: drafting a pt-br paragraph for a Senior Go/Python/AI Engineer.",
        ]

    @staticmethod
    def _build_digest_prompt(top: list[Article], thought_log: list[str]) -> str:
        article_lines = "\n".join(
            f"- [{a.score}/10] {a.title} ({a.source}): {a.reason or a.summary[:80]}"
            for a in top
        )
        thought_context = (
            "\n\nReasoning steps (sequential-thinking):\n" + "\n".join(thought_log)
            if thought_log
            else ""
        )
        return (
            f"You are a Senior Software Engineer curator. Summarize today's RSS batch."
            f"{thought_context}\n\n"
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
