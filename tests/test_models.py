from datetime import datetime

import pytest

from distill_rss.models import AppConfig, Article, Digest, FeedConfig, TopPick


class TestArticleEffectiveDate:
    def _base(self, **kwargs) -> Article:
        params = {"published": "", **kwargs}
        return Article(title="t", link="l", summary="s", source="src", **params)

    def test_uses_run_date_when_present(self):
        assert self._base(published="2024-01-01", run_date="2024-03-15").effective_date == "2024-03-15"

    def test_falls_back_to_analyzed_at_when_run_date_missing(self):
        assert self._base(published="2024-01-01", analyzed_at="2024-03-10T12:00:00").effective_date == "2024-03-10"

    def test_falls_back_to_published_when_both_missing(self):
        assert self._base(published="2024-02-20").effective_date == "2024-02-20"

    def test_falls_back_to_today_when_all_empty(self):
        today = datetime.now().strftime("%Y-%m-%d")
        assert self._base().effective_date == today

    def test_run_date_takes_priority_over_analyzed_at(self):
        a = self._base(run_date="2024-05-01", analyzed_at="2024-04-01T00:00:00")
        assert a.effective_date == "2024-05-01"

    def test_published_too_short_falls_back_to_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        assert self._base(published="2024").effective_date == today

    @pytest.mark.parametrize("run_date,analyzed_at,published,expected", [
        ("2024-05-01", "2024-04-01T00:00:00", "2024-03-01", "2024-05-01"),  # run_date wins
        ("",          "2024-04-01T12:00:00", "2024-03-01", "2024-04-01"),   # analyzed_at
        ("",          "",                    "2024-03-01", "2024-03-01"),   # published
    ])
    def test_effective_date_fallback_chain(
        self, run_date: str, analyzed_at: str, published: str, expected: str
    ):
        a = Article(
            title="t", link="l", summary="s", source="src",
            published=published, run_date=run_date, analyzed_at=analyzed_at,
        )
        assert a.effective_date == expected


class TestArticleSerialization:
    def _make_full_article(self) -> Article:
        return Article(
            title="Hello",
            link="http://x.com",
            summary="A summary",
            source="Blog",
            published="2024-01-01",
            score=8,
            reason="Very relevant",
            tags=["ai", "rag"],
            run_date="2024-01-01",
            analyzed_at="2024-01-01T10:00:00",
        )

    def test_to_dict_contains_all_fields(self):
        a = self._make_full_article()
        d = a.to_dict()
        assert d["title"] == "Hello"
        assert d["score"] == 8
        assert d["tags"] == ["ai", "rag"]

    def test_from_dict_to_dict_roundtrip(self):
        original = self._make_full_article()
        restored = Article.from_dict(original.to_dict())
        assert restored == original

    def test_from_dict_applies_defaults_for_optional_fields(self):
        a = Article.from_dict({"title": "T", "link": "L", "source": "S", "published": "P"})
        assert a.score == 0
        assert a.reason == ""
        assert a.tags == []
        assert a.run_date == ""
        assert a.analyzed_at == ""

    def test_from_dict_coerces_score_to_int(self):
        a = Article.from_dict(
            {"title": "T", "link": "L", "source": "S", "published": "", "score": "7"}
        )
        assert a.score == 7
        assert isinstance(a.score, int)


class TestTopPickSerialization:
    def test_roundtrip(self):
        p = TopPick(title="Must Read", reason="Great insights")
        assert TopPick.from_dict(p.to_dict()) == p

    def test_from_dict_handles_missing_keys(self):
        p = TopPick.from_dict({})
        assert p.title == ""
        assert p.reason == ""


class TestDigestSerialization:
    def test_roundtrip(self):
        d = Digest(
            main_themes=["AI", "LLMs"],
            novelties=["GPT-5 released"],
            top_picks=[TopPick(title="T", reason="R")],
            summary="Um resumo em pt-br",
        )
        restored = Digest.from_dict(d.to_dict())
        assert restored.main_themes == ["AI", "LLMs"]
        assert restored.novelties == ["GPT-5 released"]
        assert restored.top_picks[0].title == "T"
        assert restored.summary == "Um resumo em pt-br"

    def test_from_dict_empty_digest(self):
        d = Digest.from_dict({})
        assert d.main_themes == []
        assert d.top_picks == []
        assert d.summary == ""


class TestAppConfig:
    def test_from_dict_parses_feeds_and_keywords(self):
        data = {
            "feeds": [{"name": "Blog", "url": "http://example.com/feed"}],
            "keywords": ["python", "ai"],
        }
        cfg = AppConfig.from_dict(data)
        assert len(cfg.feeds) == 1
        assert cfg.feeds[0].name == "Blog"
        assert cfg.feeds[0].url == "http://example.com/feed"
        assert cfg.keywords == ["python", "ai"]

    def test_from_dict_empty_returns_defaults(self):
        cfg = AppConfig.from_dict({})
        assert cfg.feeds == []
        assert cfg.keywords == []
