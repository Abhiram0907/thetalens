"""Newsletter-style HTML export — plain-language research retained from agent."""

from __future__ import annotations

import html

from app.schemas.research_brief import ResearchBrief
from app.schemas.research_report import ResearchReport
from app.services.export_context_html import sector_ytd_bars_svg
from app.services.export_detail import build_export_shareable_line


def _esc(text: str | None) -> str:
    return html.escape(text or "", quote=True)


def _direction_class(direction: str) -> str:
    d = direction.lower()
    if "bull" in d:
        return "bullish"
    if "bear" in d:
        return "bearish"
    return "neutral"


def _section(title: str, body_html: str, extra: str = "") -> str:
    return f"""
      <section class="newsletter-section">
        <h2 class="section-kicker">{_esc(title)}</h2>
        {extra}
        <div class="md-body">{body_html}</div>
      </section>"""


def _bullets(items: list[str], css_class: str) -> str:
    if not items:
        return '<p class="md-body">—</p>'
    lis = "".join(f"<li>{_esc(b)}</li>" for b in items)
    return f'<ul class="{css_class}">{lis}</ul>'


def render_research_report_html(report: ResearchReport) -> str:
    view = report.parsed_view
    ticker = view.underlying.upper()
    generated = report.generated_at.strftime("%B %d, %Y")
    dir_class = _direction_class(view.direction)
    brief: ResearchBrief = report.research_brief or ResearchBrief()

    chart_html = ""
    if report.market_intel and report.market_intel.sector:
        s = report.market_intel.sector
        chart_html = f"""
        <div class="sector-chart-wrap">
          {sector_ytd_bars_svg(s.sector_etfs, s.benchmark_return_pct, s.ticker_return_pct)}
        </div>"""

    s1_body = f'<p>{_esc(brief.stock_doing)}</p>' if brief.stock_doing else "<p>—</p>"
    s1 = _section("What's the stock doing?", s1_body, chart_html)
    mood_body = f'<p>{_esc(brief.mood)}</p>' if brief.mood else "<p>—</p>"
    if report.sentiment_headlines:
        headline_lis: list[str] = []
        for h in report.sentiment_headlines[:3]:
            src = f' <span class="headline-src">({_esc(h.source)})</span>' if h.source else ""
            headline_lis.append(f"<li>{_esc(h.title)}{src}</li>")
        mood_body += f'<ul class="headline-list">{"".join(headline_lis)}</ul>'
    s2 = _section("What's the mood?", mood_body)
    s3 = _section(
        "What could move it?",
        f'<p>{_esc(brief.could_move)}</p>' if brief.could_move else "<p>—</p>",
    )
    s4 = _section(
        "What's working for this thesis?",
        _bullets(brief.working_for, "thesis-pros"),
    )
    s5 = _section(
        "What's working against it?",
        _bullets(brief.working_against, "thesis-cons"),
    )

    bottom_html = ""
    bottom_text = brief.bottom_line or report.so_what_box or ""
    if bottom_text:
        bottom_html = f"""
      <aside class="so-what-box so-what-box--closer" role="note">
        <p class="so-what-label">Bottom line</p>
        <p class="so-what-text">{_esc(bottom_text)}</p>
      </aside>"""

    shareable = build_export_shareable_line(report) or report.shareable_line
    shareable_html = ""
    if shareable:
        shareable_html = f"""
      <p class="shareable-line" title="Copy for journal or chat">{_esc(shareable)}</p>"""

    data_note = report.data_as_of_display or "Modeled via yfinance — verify live quotes"
    if report.data_provenance.data_age_warning:
        data_note = f"{data_note} {report.data_provenance.data_age_warning}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>State of the Play — {ticker} · ThetaLens</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
  <style>
    :root {{
      --ink: #f4f0e6;
      --paper: #0d0d0d;
      --paper-deep: #1a1814;
      --gold: #9a7b2f;
      --gold-bright: #c9a655;
      --rule: rgba(255, 255, 255, 0.12);
      --muted: #8a8478;
      --bull: #3dd68c;
      --bear: #ff6b6b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "DM Sans", system-ui, sans-serif;
      background: #0d0d0d;
      color: var(--ink);
      line-height: 1.5;
      padding: 24px 16px 48px;
    }}
    .newsletter {{
      max-width: 680px;
      margin: 0 auto;
      background: var(--paper);
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 0 40px rgba(154, 123, 47, 0.06);
    }}
    .poster {{
      background: linear-gradient(165deg, #0d0d0d 0%, #1a1814 55%, #2a2418 100%);
      color: #f4f0e6;
      padding: 36px 28px 32px;
      text-align: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .masthead {{
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 9px;
      letter-spacing: 0.35em;
      text-transform: uppercase;
      opacity: 0.7;
      margin-bottom: 8px;
    }}
    .state-title {{
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: clamp(2rem, 6vw, 2.75rem);
      font-weight: 700;
      letter-spacing: 0.02em;
      margin-bottom: 4px;
    }}
    .state-sub {{ font-size: 0.85rem; opacity: 0.75; margin-bottom: 20px; }}
    .ticker-display {{
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 2.5rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
    }}
    .direction-pill {{
      display: inline-block;
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 11px;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      padding: 6px 16px;
      border-radius: 2px;
      margin-bottom: 20px;
    }}
    .direction-pill.bullish {{ background: rgba(61, 214, 140, 0.2); color: #7dffb8; border: 1px solid #3dd68c; }}
    .direction-pill.bearish {{ background: rgba(255, 107, 107, 0.2); color: #ffb0b0; border: 1px solid #ff6b6b; }}
    .direction-pill.neutral {{ background: rgba(201, 166, 85, 0.2); color: var(--gold-bright); border: 1px solid var(--gold-bright); }}
    .stat-strip {{
      display: table;
      width: 100%;
      max-width: 420px;
      margin: 8px auto 0;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .stat-row {{ display: table-row; }}
    .stat {{
      display: table-cell;
      background: rgba(0,0,0,0.35);
      padding: 12px 8px;
      text-align: center;
      border-right: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .stat:last-child {{ border-right: none; }}
    .stat-label {{
      font-size: 9px;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      opacity: 0.65;
      display: block;
      margin-bottom: 4px;
    }}
    .stat-value {{
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 13px;
      font-weight: 500;
    }}
    .body-pad {{ padding: 28px 24px 32px; }}
    .section-kicker {{
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 10px;
      letter-spacing: 0.28em;
      text-transform: uppercase;
      color: var(--gold);
      border-bottom: 1px solid var(--rule);
      padding-bottom: 8px;
      margin-bottom: 16px;
    }}
    .newsletter-section {{ margin-bottom: 28px; }}
    .md-body {{
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 1.05rem;
      line-height: 1.5;
      color: var(--ink);
    }}
    .md-body h2, .md-body h3 {{
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 1.15rem;
      font-weight: 600;
      margin: 18px 0 8px;
      color: var(--ink);
    }}
    .md-body h2:first-child, .md-body h3:first-child {{ margin-top: 0; }}
    .md-body p {{ margin-bottom: 10px; }}
    .md-body p:last-child {{ margin-bottom: 0; }}
    .md-body ul, .md-body ol {{ margin: 8px 0 12px 20px; }}
    .md-body li {{ margin-bottom: 4px; }}
    .md-body strong {{ font-weight: 600; }}
    .thesis-pros, .thesis-cons {{
      list-style: none;
      margin: 0;
      padding: 0;
      font-family: "Cormorant Garamond", Georgia, serif;
    }}
    .thesis-pros li, .thesis-cons li {{
      font-size: 1.02rem;
      line-height: 1.45;
      padding: 10px 12px;
      margin-bottom: 8px;
      border-left: 4px solid var(--bull);
      background: var(--paper-deep);
    }}
    .thesis-cons li {{ border-left-color: var(--bear); }}
    .headline-list {{
      list-style: none;
      margin: 12px 0 0;
      padding: 0;
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 0.98rem;
    }}
    .headline-list li {{
      padding: 8px 10px;
      margin-bottom: 6px;
      background: var(--paper-deep);
      border-left: 3px solid var(--gold);
    }}
    .headline-src {{ color: var(--muted); font-size: 0.85em; }}
    .sector-chart-wrap {{ margin: 12px 0 4px; }}
    .sector-bars-svg {{ max-width: 100%; height: auto; display: block; }}
    .so-what-box {{
      background: #1a1814;
      color: var(--ink);
      border: 1px solid rgba(201, 166, 85, 0.2);
      padding: 18px 20px;
      margin-bottom: 24px;
    }}
    .so-what-box--closer {{ margin-top: 8px; }}
    .so-what-label {{
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 9px;
      letter-spacing: 0.28em;
      text-transform: uppercase;
      color: var(--gold-bright);
      margin-bottom: 10px;
    }}
    .so-what-text {{
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 1.45rem;
      line-height: 1.4;
      font-weight: 400;
    }}
    .shareable-line {{
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 10px;
      background: #1a1814;
      color: var(--ink);
      padding: 10px 12px;
      margin-bottom: 18px;
      border: 1px solid rgba(201, 166, 85, 0.35);
      border-radius: 2px;
      word-break: break-word;
      user-select: all;
    }}
    .footer-note {{
      margin-top: 8px;
      padding-top: 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 0.72rem;
      color: var(--muted);
      line-height: 1.45;
    }}
    .brand-footer {{
      text-align: center;
      font-family: "DM Mono", ui-monospace, monospace;
      font-size: 9px;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      margin-top: 20px;
      color: var(--muted);
    }}
    @media print {{
      :root {{
        --ink: #0a0a0a;
        --paper: #ffffff;
        --paper-deep: #f4f0e6;
        --rule: #1a1a1a;
        --muted: #5c564c;
      }}
      body {{
        background: #fff;
        color: var(--ink);
      }}
      .newsletter {{
        border: 1px solid #ccc;
        box-shadow: none;
      }}
      .poster {{
        background: #f4f0e6;
        color: #0a0a0a;
        border-bottom: 1px solid #ccc;
      }}
      .direction-pill.bullish {{ color: #1a5c3a; border-color: #1a5c3a; }}
      .direction-pill.bearish {{ color: #6b1f1f; border-color: #6b1f1f; }}
      .so-what-box, .shareable-line, .thesis-pros li, .thesis-cons li {{
        background: #f4f0e6;
        border-color: #ccc;
        color: #0a0a0a;
      }}
    }}
  </style>
</head>
<body>
  <div class="newsletter">
    <header class="poster">
      <div class="poster-inner">
        <p class="masthead">ThetaLens · Options intelligence</p>
        <h1 class="state-title">State of the Play</h1>
        <p class="state-sub">{generated}</p>
        <div class="ticker-display">{_esc(ticker)}</div>
        <span class="direction-pill {dir_class}">{_esc(view.direction)} {view.direction_icon}</span>
        <div class="stat-strip">
          <div class="stat-row">
            <div class="stat">
              <span class="stat-label">Spot</span>
              <span class="stat-value">${view.underlying_price:.2f}</span>
            </div>
            <div class="stat">
              <span class="stat-label">Horizon</span>
              <span class="stat-value">{_esc(view.horizon_label)}</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="body-pad">
      {s1}
      {s2}
      {s3}
      {s4}
      {s5}
      {bottom_html}
      {shareable_html}
      <p class="footer-note">{_esc(data_note)} · {_esc(report.disclaimer)}</p>
      <p class="brand-footer">thetalens.app · Educational research only</p>
    </div>
  </div>
</body>
</html>"""
