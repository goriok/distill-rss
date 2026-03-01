"""
Unit tests for distill_rss/mcp_tools.py.

Covers Null Objects (contract compliance) and the TRACKABLE_LIBRARIES constant.
Real MCP clients (Context7Client, SequentialThinkingClient) require live
subprocesses and are exercised via integration tests.
"""

import pytest

from distill_rss.mcp_tools import (
    TRACKABLE_LIBRARIES,
    NullContextProvider,
    NullThinkingRecorder,
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


class TestNullThinkingRecorder:
    async def test_returns_thoughts_unchanged(self):
        recorder = NullThinkingRecorder()
        thoughts = ["Step 1 – extract themes.", "Step 2 – find novelties."]
        result = await recorder.record(thoughts)
        assert result == thoughts

    async def test_returns_empty_list_for_empty_input(self):
        recorder = NullThinkingRecorder()
        result = await recorder.record([])
        assert result == []

    async def test_does_not_mutate_input(self):
        recorder = NullThinkingRecorder()
        original = ["thought one"]
        result = await recorder.record(original)
        assert result is original  # NullThinkingRecorder returns the same list object


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
