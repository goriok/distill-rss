import json

import pytest

from distill_rss.models import Article, Digest, TopPick
from distill_rss.persistence import ConfigLoader, JsonArticleRepository, JsonDigestRepository


@pytest.fixture
def sample_article() -> Article:
    return Article(
        title="Test Article",
        link="http://test.com",
        summary="A test summary",
        source="Test Blog",
        published="2024-01-01",
        score=7,
        reason="Relevant content",
        tags=["ai"],
        run_date="2024-01-01",
    )


@pytest.fixture
def sample_digest() -> Digest:
    return Digest(
        main_themes=["AI", "Agents"],
        novelties=["New model released"],
        top_picks=[TopPick(title="Top Article", reason="Very relevant")],
        summary="Um resumo em português.",
    )


class TestJsonArticleRepository:
    def test_load_returns_empty_list_when_file_does_not_exist(self, tmp_path):
        repo = JsonArticleRepository(tmp_path / "history.json")
        assert repo.load() == []

    def test_load_returns_empty_list_on_corrupt_json(self, tmp_path):
        path = tmp_path / "history.json"
        path.write_text("not valid json", encoding="utf-8")
        repo = JsonArticleRepository(path)
        assert repo.load() == []

    def test_save_creates_file_with_valid_json(self, tmp_path, sample_article):
        path = tmp_path / "history.json"
        repo = JsonArticleRepository(path)
        repo.save([sample_article])

        assert path.exists()
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert data[0]["title"] == "Test Article"

    def test_save_and_load_roundtrip(self, tmp_path, sample_article):
        repo = JsonArticleRepository(tmp_path / "history.json")
        repo.save([sample_article])
        loaded = repo.load()

        assert len(loaded) == 1
        assert loaded[0].title == sample_article.title
        assert loaded[0].score == sample_article.score
        assert loaded[0].tags == sample_article.tags

    def test_save_multiple_articles_preserves_order(self, tmp_path):
        repo = JsonArticleRepository(tmp_path / "history.json")
        articles = [
            Article(title=f"Article {i}", link=f"http://{i}.com", summary="", source="S", published="")
            for i in range(3)
        ]
        repo.save(articles)
        loaded = repo.load()

        assert [a.title for a in loaded] == ["Article 0", "Article 1", "Article 2"]


class TestJsonDigestRepository:
    def test_load_returns_empty_dict_when_file_does_not_exist(self, tmp_path):
        repo = JsonDigestRepository(tmp_path / "digests.json")
        assert repo.load() == {}

    def test_load_returns_empty_dict_on_corrupt_json(self, tmp_path):
        path = tmp_path / "digests.json"
        path.write_text("{bad json", encoding="utf-8")
        repo = JsonDigestRepository(path)
        assert repo.load() == {}

    def test_save_and_load_roundtrip(self, tmp_path, sample_digest):
        repo = JsonDigestRepository(tmp_path / "digests.json")
        repo.save({"2024-01-01": sample_digest})
        loaded = repo.load()

        assert "2024-01-01" in loaded
        d = loaded["2024-01-01"]
        assert d.main_themes == ["AI", "Agents"]
        assert d.top_picks[0].title == "Top Article"
        assert d.summary == "Um resumo em português."

    def test_save_creates_valid_json_structure(self, tmp_path, sample_digest):
        path = tmp_path / "digests.json"
        repo = JsonDigestRepository(path)
        repo.save({"2024-01-01": sample_digest})

        raw = json.loads(path.read_text())
        assert "2024-01-01" in raw
        assert isinstance(raw["2024-01-01"]["main_themes"], list)


class TestConfigLoader:
    def test_load_valid_config(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps({
                "feeds": [{"name": "Blog", "url": "http://example.com/rss"}],
                "keywords": ["python", "ai"],
            }),
            encoding="utf-8",
        )
        cfg = ConfigLoader(cfg_path).load()

        assert len(cfg.feeds) == 1
        assert cfg.feeds[0].name == "Blog"
        assert cfg.feeds[0].url == "http://example.com/rss"
        assert "python" in cfg.keywords

    def test_load_missing_file_returns_empty_config(self, tmp_path):
        cfg = ConfigLoader(tmp_path / "nonexistent.json").load()
        assert cfg.feeds == []
        assert cfg.keywords == []

    def test_load_corrupt_json_returns_empty_config(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("not json", encoding="utf-8")
        cfg = ConfigLoader(cfg_path).load()
        assert cfg.feeds == []
        assert cfg.keywords == []

    def test_load_multiple_feeds(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps({
                "feeds": [
                    {"name": "A", "url": "http://a.com"},
                    {"name": "B", "url": "http://b.com"},
                ],
                "keywords": [],
            }),
            encoding="utf-8",
        )
        cfg = ConfigLoader(cfg_path).load()
        assert len(cfg.feeds) == 2
        assert cfg.feeds[1].name == "B"
