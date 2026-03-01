"""
MCP tool wrappers with explicit Protocols and Null Objects.

Design decisions:
- LibraryContextProvider / ThinkingRecorder are Protocols (structural typing).
  Concrete classes don't need to inherit from them; duck typing + mypy cover it.
- Null Object pattern: NullContextProvider / NullThinkingRecorder let callers
  skip the MCP wiring entirely without if-guards at every call site.
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


@runtime_checkable
class ThinkingRecorder(Protocol):
    async def record(self, thoughts: list[str]) -> list[str]: ...


# ── Null Objects ──────────────────────────────────────────────────────────────

class NullContextProvider:
    """Used when context7 MCP is unavailable — keeps caller code clean."""

    async def get_context(self, text: str) -> str:
        return ""


class NullThinkingRecorder:
    """Used when sequential-thinking MCP is unavailable."""

    async def record(self, thoughts: list[str]) -> list[str]:
        return thoughts


# ── Real implementations ──────────────────────────────────────────────────────

class Context7Client:
    """
    Resolves library names → context7 IDs → fetches current doc snippets.
    Enriches AI prompts with up-to-date library documentation.
    """

    def __init__(self, session: ClientSession):
        self._session = session

    async def get_context(self, text: str) -> str:
        text_lower = text.lower()
        for lib in TRACKABLE_LIBRARIES:
            if lib not in text_lower:
                continue
            try:
                snippet = await self._fetch_snippet(lib)
                if snippet:
                    return f"[context7 – {lib} docs]: {snippet}"
            except Exception as exc:
                logger.debug("context7 lookup failed for %s: %s", lib, exc)
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


class SequentialThinkingClient:
    """
    Records structured reasoning steps via the sequential-thinking MCP server.
    Returns the server's enriched responses for digest prompt injection.
    """

    def __init__(self, session: ClientSession):
        self._session = session

    async def record(self, thoughts: list[str]) -> list[str]:
        results: list[str] = []
        total = len(thoughts)
        for i, thought in enumerate(thoughts, 1):
            try:
                result = await self._session.call_tool(
                    "sequentialthinking",
                    arguments={
                        "thought": thought,
                        "thoughtNumber": i,
                        "totalThoughts": total,
                        "nextThoughtNeeded": i < total,
                    },
                )
                results.append(result.content[0].text if result.content else thought)
            except Exception as exc:
                logger.debug("sequential-thinking step %d failed: %s", i, exc)
                results.append(thought)
        return results
