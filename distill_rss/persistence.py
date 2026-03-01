"""
Persistence layer using the Repository pattern.

Each repository is defined by a Protocol (interface) and implemented as a
concrete JSON-backed class. Callers depend on the Protocol, not the
implementation — satisfying the Dependency Inversion Principle.
"""

import json
import logging
from pathlib import Path
from typing import Protocol

from .models import AppConfig, Article, Digest

logger = logging.getLogger(__name__)


# ── Protocols (interfaces) ────────────────────────────────────────────────────

class ArticleRepository(Protocol):
    def load(self) -> list[Article]: ...
    def save(self, articles: list[Article]) -> None: ...


class DigestRepository(Protocol):
    def load(self) -> dict[str, Digest]: ...
    def save(self, digests: dict[str, Digest]) -> None: ...


# ── JSON implementations ──────────────────────────────────────────────────────

class JsonArticleRepository:
    def __init__(self, path: Path = Path("history.json")):
        self.path = path

    def load(self) -> list[Article]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [Article.from_dict(a) for a in data]
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Could not load %s: %s", self.path, exc)
            return []

    def save(self, articles: list[Article]) -> None:
        self.path.write_text(
            json.dumps([a.to_dict() for a in articles], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


class JsonDigestRepository:
    def __init__(self, path: Path = Path("digests.json")):
        self.path = path

    def load(self) -> dict[str, Digest]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {date: Digest.from_dict(d) for date, d in data.items()}
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Could not load %s: %s", self.path, exc)
            return {}

    def save(self, digests: dict[str, Digest]) -> None:
        self.path.write_text(
            json.dumps(
                {date: d.to_dict() for date, d in digests.items()},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


class ConfigLoader:
    def __init__(self, path: Path = Path("config.json")):
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            logger.warning("Config file not found: %s", self.path)
            return AppConfig(feeds=[], keywords=[])
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return AppConfig.from_dict(data)
        except json.JSONDecodeError as exc:
            logger.error("Error decoding %s: %s", self.path, exc)
            return AppConfig(feeds=[], keywords=[])
