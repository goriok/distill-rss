"""
HTML report generation — Single Responsibility: render only.

HTMLReportGenerator is the only class here; it has no knowledge of how data
is fetched or stored. Pure input → HTML output.
"""

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .constants import HIGH_SCORE_THRESHOLD, MIN_ACCEPTED_SCORE
from .models import Article, Digest


class ScoreCategory(StrEnum):
    """CSS class names for score colour-coding in the report."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_score(cls, score: int) -> "ScoreCategory":
        if score >= HIGH_SCORE_THRESHOLD:
            return cls.HIGH
        if score >= MIN_ACCEPTED_SCORE:
            return cls.MEDIUM
        return cls.LOW


def _render_digest(digest: Digest | None) -> str:
    if not digest:
        return ""

    themes = "".join(f'<span class="tag">{t}</span>' for t in digest.main_themes)
    novelties = "".join(f"<li>{n}</li>" for n in digest.novelties)
    picks = "".join(
        f"<li><strong>{p.title}</strong> — {p.reason}</li>"
        for p in digest.top_picks
    )
    summary = digest.summary

    novelties_block = (
        f"<div><strong>Novidades:</strong><ul>{novelties}</ul></div>" if novelties else ""
    )
    picks_block = (
        f"<div><strong>Top Picks:</strong><ul>{picks}</ul></div>" if picks else ""
    )
    summary_block = (
        f"<div class='summary'><strong>Resumo:</strong> {summary}</div>" if summary else ""
    )

    return (
        f'<div class="digest-box">'
        f"<div><strong>Temas:</strong> {themes}</div>"
        f"{novelties_block}"
        f"{picks_block}"
        f"{summary_block}"
        f"</div>"
    )


_CSS = """
    :root{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--text:#e2e8f0;--muted:#8892a4;--green:#4ade80;--yellow:#fbbf24;--red:#f87171;--accent:#818cf8}
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:14px}
    a{color:var(--accent);text-decoration:none}
    a:hover{text-decoration:underline}
    #top{position:sticky;top:0;z-index:100;background:var(--surface);border-bottom:1px solid var(--border);padding:12px 20px}
    #top h1{font-size:1.2rem;color:var(--accent);display:inline}
    .meta{margin-left:12px;color:var(--muted);font-size:12px}
    .day-nav{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px}
    .day-nav a{background:var(--border);border-radius:4px;padding:3px 10px;font-size:12px;color:var(--text)}
    .day-nav a:hover{background:var(--accent);color:#fff;text-decoration:none}
    .badge{background:var(--accent);color:#fff;border-radius:10px;padding:1px 7px;font-size:11px;font-weight:600}
    .day-section{max-width:1400px;margin:24px auto;padding:0 16px}
    .day-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
    .day-header h2{font-size:1.1rem;color:var(--accent)}
    .top-link{margin-left:auto;font-size:12px;color:var(--muted)}
    .digest-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 18px;margin-bottom:16px;line-height:1.6}
    .digest-box>div{margin-bottom:8px}
    .digest-box ul{padding-left:18px}
    .digest-box li{margin-bottom:4px}
    .digest-box .summary{color:var(--muted);font-style:italic}
    .tag{background:#2a2d3a;border-radius:3px;padding:1px 6px;font-size:11px;margin-left:4px;color:var(--muted)}
    table{width:100%;border-collapse:collapse;background:var(--surface);border-radius:8px;overflow:hidden;border:1px solid var(--border)}
    th{background:#22253a;padding:8px 12px;text-align:left;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
    td{padding:8px 12px;border-top:1px solid var(--border);vertical-align:top}
    tr:hover td{background:#1e2130}
    .score{font-weight:700;text-align:center;width:50px}
    .score-high{color:var(--green)}
    .score-medium{color:var(--yellow)}
    .score-low{color:var(--red)}
"""


class HTMLReportGenerator:
    """Generates a dark-theme HTML report paginated by run date."""

    def __init__(self, output_path: Path = Path("rss_report.html")):
        self.output_path = output_path

    def generate(
        self,
        articles: list[Article],
        digests: dict[str, Digest] | None = None,
    ) -> Path:
        if digests is None:
            digests = {}

        days: dict[str, list[Article]] = {}
        for article in articles:
            days.setdefault(article.effective_date, []).append(article)

        sorted_days = sorted(days.keys(), reverse=True)
        nav = self._render_nav(sorted_days, days)
        sections = self._render_sections(sorted_days, days, digests)

        html = self._build_html(
            nav=nav,
            sections=sections,
            total=len(articles),
            day_count=len(sorted_days),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        self.output_path.write_text(html, encoding="utf-8")
        return self.output_path

    def _render_nav(self, sorted_days: list[str], days: dict[str, list[Article]]) -> str:
        return "\n".join(
            f'<a href="#day-{d}">{d} <span class="badge">{len(days[d])}</span></a>'
            for d in sorted_days
        )

    def _render_sections(
        self,
        sorted_days: list[str],
        days: dict[str, list[Article]],
        digests: dict[str, Digest],
    ) -> str:
        def _section(day: str) -> str:
            day_arts = sorted(days[day], key=lambda a: a.score, reverse=True)
            return (
                f'<section id="day-{day}" class="day-section">'
                f'<div class="day-header">'
                f"<h2>{day}</h2>"
                f'<span class="badge">{len(day_arts)} artigos</span>'
                f'<a class="top-link" href="#top">↑ topo</a>'
                f"</div>"
                f"{_render_digest(digests.get(day))}"
                f"<table>"
                f"<thead><tr><th>Score</th><th>Título</th><th>Fonte</th><th>Resumo / Tags</th><th>Link</th></tr></thead>"
                f"<tbody>{self._render_rows(day_arts)}</tbody>"
                f"</table>"
                f"</section>"
            )

        return "".join(_section(day) for day in sorted_days)

    def _render_rows(self, articles: list[Article]) -> str:
        def _row(a: Article) -> str:
            tags = "".join(f'<span class="tag">{t}</span>' for t in a.tags)
            reason = a.reason or f"{a.summary[:200]}..."
            return (
                f"<tr>"
                f'<td class="score score-{ScoreCategory.from_score(a.score)}">{a.score}</td>'
                f"<td>{a.title}</td>"
                f"<td>{a.source}</td>"
                f"<td>{reason} {tags}</td>"
                f'<td><a href="{a.link}" target="_blank">↗</a></td>'
                f"</tr>"
            )

        return "".join(_row(a) for a in articles)

    @staticmethod
    def _build_html(nav: str, sections: str, total: int, day_count: int, timestamp: str) -> str:
        return (
            '<!DOCTYPE html>\n'
            '<html lang="pt-br">\n'
            '<head>\n'
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '  <title>Distill RSS</title>\n'
            f'  <style>{_CSS}</style>\n'
            '</head>\n'
            '<body>\n'
            '<header id="top">\n'
            '  <h1>📡 Distill RSS</h1>\n'
            f'  <span class="meta">{total} artigos · {day_count} dias · {timestamp}</span>\n'
            f'  <nav class="day-nav">{nav}</nav>\n'
            '</header>\n'
            f'<main>{sections}</main>\n'
            '</body>\n'
            '</html>'
        )
