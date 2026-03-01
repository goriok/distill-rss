"""
Domain models for Distill RSS.

All external data (JSON dicts from feedparser, Gemini, persisted files) is
converted into typed dataclasses at the boundary so the rest of the codebase
works with structured objects instead of raw dicts.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FeedConfig:
    name: str
    url: str


@dataclass
class AppConfig:
    feeds: list[FeedConfig]
    keywords: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        feeds = [FeedConfig(name=f["name"], url=f["url"]) for f in data.get("feeds", [])]
        return cls(feeds=feeds, keywords=data.get("keywords", []))


@dataclass
class Article:
    title: str
    link: str
    summary: str
    source: str
    published: str
    score: int = 0
    reason: str = ""
    tags: list[str] = field(default_factory=list)
    run_date: str = ""
    analyzed_at: str = ""

    @property
    def effective_date(self) -> str:
        """Fallback chain: run_date → analyzed_at[:10] → published[:10] → today."""
        if self.run_date:
            return self.run_date
        if self.analyzed_at:
            return self.analyzed_at[:10]
        if self.published and len(self.published) >= 10:
            return self.published[:10]
        return datetime.now().strftime("%Y-%m-%d")

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "link": self.link,
            "summary": self.summary,
            "source": self.source,
            "published": self.published,
            "score": self.score,
            "reason": self.reason,
            "tags": self.tags,
            "run_date": self.run_date,
            "analyzed_at": self.analyzed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        return cls(
            title=data["title"],
            link=data["link"],
            summary=data.get("summary", ""),
            source=data["source"],
            published=data.get("published", ""),
            score=int(data.get("score", 0)),
            reason=data.get("reason", ""),
            tags=data.get("tags", []),
            run_date=data.get("run_date", ""),
            analyzed_at=data.get("analyzed_at", ""),
        )


@dataclass
class TopPick:
    title: str
    reason: str

    def to_dict(self) -> dict:
        return {"title": self.title, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict) -> "TopPick":
        return cls(title=data.get("title", ""), reason=data.get("reason", ""))


@dataclass
class Digest:
    main_themes: list[str] = field(default_factory=list)
    novelties: list[str] = field(default_factory=list)
    top_picks: list[TopPick] = field(default_factory=list)
    summary: str = ""
    brief: str = ""

    def to_dict(self) -> dict:
        return {
            "main_themes": self.main_themes,
            "novelties": self.novelties,
            "top_picks": [p.to_dict() for p in self.top_picks],
            "summary": self.summary,
            "brief": self.brief,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Digest":
        return cls(
            main_themes=data.get("main_themes", []),
            novelties=data.get("novelties", []),
            top_picks=[TopPick.from_dict(p) for p in data.get("top_picks", [])],
            summary=data.get("summary", ""),
            brief=data.get("brief", ""),
        )
