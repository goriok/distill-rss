"""
Application-wide constants — single source of truth for all thresholds and defaults.

Using Final from typing ensures these values are treated as compile-time constants
by type checkers (mypy, pyright) and make intent explicit to readers.
"""

from typing import Final

# ── Score thresholds ───────────────────────────────────────────────────────────

MIN_ACCEPTED_SCORE: Final[int] = 4
"""Articles scoring below this are discarded before being added to history."""

HIGH_SCORE_THRESHOLD: Final[int] = 7
"""Articles at or above this score are rendered as "high" priority in the report."""

# ── Processing limits ──────────────────────────────────────────────────────────

MAX_DIGEST_ARTICLES: Final[int] = 25
"""Maximum number of top-scored articles sent to the digest generator."""

DEFAULT_MAX_PER_FEED: Final[int] = 5
"""Default article cap per RSS feed when no override is provided."""

# ── Prompt / API limits ────────────────────────────────────────────────────────

SUMMARY_TRUNCATE: Final[int] = 500
"""Characters of article summary included in the analysis prompt."""

SNIPPET_TRUNCATE: Final[int] = 600
"""Characters of context7 doc snippet injected into the analysis prompt."""

CONTEXT7_TOKENS: Final[int] = 800
"""Token budget requested from context7 get-library-docs."""

SEQUENTIAL_THOUGHTS: Final[int] = 4
"""Number of structured reasoning steps sent to sequential-thinking."""

# ── AI defaults ────────────────────────────────────────────────────────────────

DEFAULT_GEMINI_MODEL: Final[str] = "gemini-3-flash-preview"
"""Fallback model name when GEMINI_MODEL env-var is not set."""
