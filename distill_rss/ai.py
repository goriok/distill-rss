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
from .mcp_tools import (
    LibraryContextProvider,
    NullContextProvider,
)
from .models import Article, Digest

logger = logging.getLogger(__name__)


# ── Protocols ─────────────────────────────────────────────────────────────────


class ArticleAnalyzer(Protocol):
    async def analyze(self, article: Article, keywords: list[str]) -> dict: ...


class DigestGenerator(Protocol):
    async def generate(
        self, articles: list[Article], keywords: list[str]
    ) -> Digest | None: ...


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
        self._context_provider: LibraryContextProvider = (
            context_provider or NullContextProvider()
        )

    async def analyze(self, article: Article, keywords: list[str]) -> dict:
        if not self._matches_keywords(article, keywords):
            return {
                "score": 0,
                "reason": "Filtrado localmente (sem palavras-chave)",
                "tags": [],
            }

        library_context = await self._context_provider.get_context(
            f"{article.title} {article.summary}"
        )
        prompt = self._build_analysis_prompt(article, keywords, library_context)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
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
            f"\n\nContexto da biblioteca local (context7):\n{context}"
            if context
            else ""
        )
        return (
            "Você é o 'Agente da Práxis', curador técnico focado em uma única Diretiva Mestra: "
            "'Quantas horas de trabalho mecânico este conceito me ajuda a delegar para a máquina hoje?'\n\n"
            "Avalie o artigo abaixo. Ignore hypes e abstrações vazias. Foque em pragmatismo, "
            "implementação real (Go, Python, AI Agents) e eficiência no ecossistema de terminal (Neovim).\n\n"
            f"Palavras-chave de interesse: {', '.join(keywords)}"
            f"{ctx_block}\n\n"
            f"Título: {article.title}\n"
            f"Fonte: {article.source}\n"
            f"Resumo: {article.summary[:SUMMARY_TRUNCATE]}\n\n"
            "Responda APENAS com JSON válido. Regras para os campos:\n"
            "- 'score' (0-10): Dê 0 para 'armadilhas de produtividade' (tecnologias que geram mais complexidade e manutenção do que tempo livre). Dê 10 para 'Sinal Puro' (automação pragmática que emancipa o tempo).\n"
            "- 'reason': Uma única frase (pt-br) explicando estritamente como isso automatiza trabalho OU por que é uma armadilha burocrática.\n"
            "- 'tags': Até 3 tags focadas na aplicação (ex: 'python', 'rag-automação', 'armadilha-hype').\n\n"
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

    async def generate(
        self, articles: list[Article], keywords: list[str]
    ) -> Digest | None:
        if not articles:
            return None

        top = sorted(articles, key=lambda a: a.score, reverse=True)[
            :MAX_DIGEST_ARTICLES
        ]
        prompt = self._build_digest_prompt(top)

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
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
            "Você é o 'Agente da Práxis'. Sintetize os artigos de alto ROI lidos hoje, focando exclusivamente "
            "na emancipação do tempo e no uso da tecnologia como meio de produção para um Eng. Sênior.\n\n"
            f"Artigos Filtrados:\n{article_lines}\n\n"
            "Responda APENAS com JSON válido. Instruções de conteúdo (em pt-br):\n"
            "{\n"
            '  "brief": "<1-2 frases resumindo o ganho real de tempo/automação que a leitura de hoje proporciona>",\n'
            '  "main_themes": ["<Conceitos pragmáticos extraídos do lote>"],\n'
            '  "novelties": ["<Ideias diretas de implementação em Go/Python/Terminal derivadas dos artigos>"],\n'
            '  "top_picks": [{"title": "<t>", "reason": "<Motivo focado na remoção de servidão sistêmica>"}],\n'
            '  "summary": "<Um parágrafo de análise crítica. Aponte como as ferramentas de hoje servem à Vita Contemplativa. Se houver ruído/hype misturado no lote, denuncie-o aqui.>"\n'
            "}"
        )
