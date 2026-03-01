from pathlib import Path

import pytest

from distill_rss.models import Article, Digest, TopPick
from distill_rss.report import HTMLReportGenerator, ScoreCategory, _render_digest


def make_article(
    title: str = "Article",
    score: int = 7,
    run_date: str = "2024-01-15",
    source: str = "Blog",
    tags: list[str] | None = None,
    reason: str = "",
) -> Article:
    return Article(
        title=title,
        link=f"http://example.com/{title.lower().replace(' ', '-')}",
        summary="A test summary",
        source=source,
        published="",
        score=score,
        reason=reason,
        tags=tags or [],
        run_date=run_date,
    )


class TestScoreCategory:
    @pytest.mark.parametrize("score,expected", [
        (10, ScoreCategory.HIGH),
        (7, ScoreCategory.HIGH),
        (6, ScoreCategory.MEDIUM),
        (4, ScoreCategory.MEDIUM),
        (3, ScoreCategory.LOW),
        (0, ScoreCategory.LOW),
    ])
    def test_from_score(self, score: int, expected: ScoreCategory):
        assert ScoreCategory.from_score(score) == expected

    def test_enum_values_are_css_class_strings(self):
        assert str(ScoreCategory.HIGH) == "high"
        assert str(ScoreCategory.MEDIUM) == "medium"
        assert str(ScoreCategory.LOW) == "low"


class TestRenderDigest:
    def test_returns_empty_string_for_none(self):
        assert _render_digest(None) == ""

    def test_renders_main_themes(self):
        d = Digest(main_themes=["AI", "RAG"], novelties=[], top_picks=[], summary="")
        html = _render_digest(d)
        assert "AI" in html
        assert "RAG" in html

    def test_renders_novelties_as_list(self):
        d = Digest(main_themes=[], novelties=["New model released", "LangChain 0.3"], top_picks=[], summary="")
        html = _render_digest(d)
        assert "New model released" in html
        assert "LangChain 0.3" in html

    def test_renders_top_picks(self):
        d = Digest(
            main_themes=[], novelties=[],
            top_picks=[TopPick(title="Must Read", reason="Great insights")],
            summary="",
        )
        html = _render_digest(d)
        assert "Must Read" in html
        assert "Great insights" in html

    def test_renders_summary(self):
        d = Digest(main_themes=[], novelties=[], top_picks=[], summary="Um excelente resumo em pt-br")
        html = _render_digest(d)
        assert "Um excelente resumo em pt-br" in html

    def test_renders_brief_at_top_of_digest_box(self):
        d = Digest(main_themes=["AI"], novelties=[], top_picks=[], summary="", brief="Hoje: AI e RAG.")
        html = _render_digest(d)
        assert "Hoje: AI e RAG." in html
        assert 'class="brief"' in html
        # brief block must appear before themes block
        assert html.index("brief") < html.index("Temas")

    def test_no_brief_block_when_empty(self):
        d = Digest(main_themes=["AI"], novelties=[], top_picks=[], summary="", brief="")
        html = _render_digest(d)
        assert 'class="brief"' not in html

    def test_digest_box_css_class_present(self):
        d = Digest(main_themes=["AI"], novelties=[], top_picks=[], summary="")
        assert 'class="digest-box"' in _render_digest(d)

    def test_no_novelties_block_when_empty(self):
        d = Digest(main_themes=["AI"], novelties=[], top_picks=[], summary="")
        html = _render_digest(d)
        assert "Novidades" not in html

    def test_no_top_picks_block_when_empty(self):
        d = Digest(main_themes=["AI"], novelties=[], top_picks=[], summary="")
        html = _render_digest(d)
        assert "Top Picks" not in html


class TestHTMLReportGenerator:
    @pytest.fixture
    def generator(self, tmp_path: Path) -> HTMLReportGenerator:
        return HTMLReportGenerator(tmp_path / "report.html")

    @pytest.fixture
    def multi_day_articles(self) -> list[Article]:
        return [
            make_article("Article A", score=9, run_date="2024-01-15"),
            make_article("Article B", score=5, run_date="2024-01-15"),
            make_article("Article C", score=7, run_date="2024-01-14"),
        ]

    def test_creates_html_file(self, generator, multi_day_articles):
        path = generator.generate(multi_day_articles)
        assert path.exists()

    def test_returns_output_path(self, generator, multi_day_articles):
        path = generator.generate(multi_day_articles)
        assert path == generator.output_path

    def test_html_contains_all_article_titles(self, generator, multi_day_articles):
        generator.generate(multi_day_articles)
        content = generator.output_path.read_text()
        assert "Article A" in content
        assert "Article B" in content
        assert "Article C" in content

    def test_html_contains_day_section_anchors(self, generator, multi_day_articles):
        generator.generate(multi_day_articles)
        content = generator.output_path.read_text()
        assert 'id="day-2024-01-15"' in content
        assert 'id="day-2024-01-14"' in content

    def test_articles_sorted_by_score_descending_within_day(self, generator, multi_day_articles):
        generator.generate(multi_day_articles)
        content = generator.output_path.read_text()
        # Article A (score 9) must appear before Article B (score 5) in same day section
        assert content.index("Article A") < content.index("Article B")

    def test_newer_day_appears_before_older_day(self, generator, multi_day_articles):
        generator.generate(multi_day_articles)
        content = generator.output_path.read_text()
        assert content.index("2024-01-15") < content.index("2024-01-14")

    def test_renders_digest_when_provided(self, generator, multi_day_articles):
        digests = {
            "2024-01-15": Digest(main_themes=["AI Agents"], novelties=[], top_picks=[], summary="Resumo")
        }
        generator.generate(multi_day_articles, digests)
        content = generator.output_path.read_text()
        assert "AI Agents" in content
        assert "Resumo" in content

    def test_generates_without_digests(self, generator, multi_day_articles):
        path = generator.generate(multi_day_articles)  # no digests arg
        assert path.exists()

    def test_generates_with_empty_article_list(self, generator):
        path = generator.generate([])
        assert path.exists()
        content = generator.output_path.read_text()
        assert "0 artigos" in content

    def test_article_tags_appear_in_output(self, generator):
        articles = [make_article("Tagged Article", tags=["rag", "python"], run_date="2024-01-01")]
        generator.generate(articles)
        content = generator.output_path.read_text()
        assert "rag" in content
        assert "python" in content

    def test_score_css_class_high_applied(self, generator):
        articles = [make_article("High Score", score=9, run_date="2024-01-01")]
        generator.generate(articles)
        content = generator.output_path.read_text()
        assert "score-high" in content

    def test_score_css_class_low_applied(self, generator):
        articles = [make_article("Low Score", score=2, run_date="2024-01-01")]
        generator.generate(articles)
        content = generator.output_path.read_text()
        assert "score-low" in content

    def test_nav_links_contain_day_badges(self, generator, multi_day_articles):
        generator.generate(multi_day_articles)
        content = generator.output_path.read_text()
        # nav section should have badge spans with counts
        assert 'class="badge"' in content
