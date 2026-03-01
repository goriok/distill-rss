"""
Unit tests for distill_rss/mcp_tools.py.

Covers Null Objects (contract compliance) and the TRACKABLE_LIBRARIES constant.
Real MCP clients (Context7Client) require live subprocesses and are exercised
via integration tests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from distill_rss.mcp_tools import (
    TRACKABLE_LIBRARIES,
    Context7Client,
    NullContextProvider,
)


class TestNullContextProvider:
    async def test_returns_empty_string(self):
        provider = NullContextProvider()
        result = await provider.get_context("some article text about langchain")
        assert result == ""

    async def test_returns_empty_string_for_empty_input(self):
        provider = NullContextProvider()
        result = await provider.get_context("")
        assert result == ""

    async def test_is_idempotent(self):
        provider = NullContextProvider()
        first = await provider.get_context("text")
        second = await provider.get_context("text")
        assert first == second == ""


class TestContext7ClientCache:
    async def test_caches_snippet_for_repeated_library_calls(self):
        client = Context7Client(MagicMock())
        with patch.object(client, "_fetch_snippet", new=AsyncMock(return_value="docs overview")) as mock_fetch:
            result1 = await client.get_context("article about langchain rag")
            result2 = await client.get_context("another langchain article")

        mock_fetch.assert_called_once_with("langchain")
        assert result1 == result2 == "[context7 – langchain docs]: docs overview"

    async def test_does_not_retry_empty_or_failed_lookups(self):
        client = Context7Client(MagicMock())
        with patch.object(client, "_fetch_snippet", new=AsyncMock(return_value="")) as mock_fetch:
            result1 = await client.get_context("article about langchain")
            result2 = await client.get_context("more langchain content")

        mock_fetch.assert_called_once_with("langchain")
        assert result1 == "" and result2 == ""

    async def test_different_libraries_are_cached_independently(self):
        client = Context7Client(MagicMock())
        with patch.object(client, "_fetch_snippet", new=AsyncMock(side_effect=lambda lib: f"{lib}-docs")) as mock_fetch:
            r1 = await client.get_context("fastapi article")
            r2 = await client.get_context("pydantic article")
            r3 = await client.get_context("fastapi again")

        assert mock_fetch.call_count == 2
        assert "fastapi" in r1 and "pydantic" in r2
        assert r1 == r3


class TestTrackableLibraries:
    def test_is_nonempty(self):
        assert len(TRACKABLE_LIBRARIES) > 0

    def test_all_entries_are_strings(self):
        assert all(isinstance(lib, str) for lib in TRACKABLE_LIBRARIES)

    def test_all_entries_are_lowercase(self):
        assert all(lib == lib.lower() for lib in TRACKABLE_LIBRARIES), (
            "Library names should be lowercase to match case-insensitive text scanning"
        )

    def test_no_duplicates(self):
        assert len(TRACKABLE_LIBRARIES) == len(set(TRACKABLE_LIBRARIES))

    @pytest.mark.parametrize("lib", ["langchain", "fastapi", "pydantic", "openai", "anthropic"])
    def test_contains_known_libraries(self, lib: str):
        assert lib in TRACKABLE_LIBRARIES
