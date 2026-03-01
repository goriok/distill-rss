"""
MCP tool wrappers with explicit Protocols and Null Objects.

Design decisions:
- LibraryContextProvider is a Protocol (structural typing).
  Concrete classes don't need to inherit from it; duck typing + mypy cover it.
- Null Object pattern: NullContextProvider lets callers skip the MCP wiring
  entirely without if-guards at every call site.
- Each class manages exactly ONE concern (ISP / SRP).

Important: these sessions are spawned BY us (stdio subprocesses). We never
stop processes we did not start (CodeCompanion's instances are independent).
"""

import json
import logging
from typing import Final, Protocol, runtime_checkable

from mcp import ClientSession

from .constants import CONTEXT7_TOKENS, SNIPPET_TRUNCATE

logger = logging.getLogger(__name__)

TRACKABLE_LIBRARIES: Final[list[str]] = [
    "langchain", "langgraph", "llamaindex", "llama-index",
    "fastapi", "pydantic", "sqlalchemy",
    "autogen", "crewai", "dspy", "smolagents",
    "ollama", "vllm", "transformers",
    "weaviate", "qdrant", "pinecone", "chroma", "chromadb",
    "openai", "anthropic", "google-genai",
    "codecompanion", "neovim",
]


# ── Protocols ─────────────────────────────────────────────────────────────────

@runtime_checkable
class LibraryContextProvider(Protocol):
    async def get_context(self, text: str) -> str: ...


# ── Null Objects ──────────────────────────────────────────────────────────────

class NullContextProvider:
    """Used when context7 MCP is unavailable — keeps caller code clean."""

    async def get_context(self, text: str) -> str:
        return ""


# ── Real implementations ──────────────────────────────────────────────────────

class Context7Client:
    """
    Resolves library names → context7 IDs → fetches current doc snippets.
    Enriches AI prompts with up-to-date library documentation.

    Results are cached per library for the lifetime of the client, so multiple
    articles mentioning the same library share a single MCP roundtrip.
    """

    def __init__(self, session: ClientSession):
        self._session = session
        self._cache: dict[str, str] = {}  # lib → snippet ("" means no result / failed)

    async def get_context(self, text: str) -> str:
        text_lower = text.lower()
        for lib in TRACKABLE_LIBRARIES:
            if lib not in text_lower:
                continue
            if lib not in self._cache:
                try:
                    self._cache[lib] = await self._fetch_snippet(lib)
                except Exception as exc:
                    logger.debug("context7 lookup failed for %s: %s", lib, exc)
                    self._cache[lib] = ""
            snippet = self._cache[lib]
            if snippet:
                return f"[context7 – {lib} docs]: {snippet}"
        return ""

    async def _fetch_snippet(self, lib: str) -> str:
        resolve = await self._session.call_tool(
            "resolve-library-id",
            arguments={"libraryName": lib},
        )
        if not resolve.content:
            return ""

        data = json.loads(resolve.content[0].text)
        results = data.get("results") or []
        lib_id = results[0].get("id") if results else data.get("id")
        if not lib_id:
            return ""

        docs = await self._session.call_tool(
            "get-library-docs",
            arguments={
                "context7CompatibleLibraryID": lib_id,
                "topic": "overview",
                "tokens": CONTEXT7_TOKENS,
            },
        )
        return docs.content[0].text[:SNIPPET_TRUNCATE] if docs.content else ""


