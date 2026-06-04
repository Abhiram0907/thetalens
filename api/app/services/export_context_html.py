"""SVG helpers for market context in research exports."""

from __future__ import annotations

import html

from app.schemas.market_intel import YtdReturnBar


def _esc(text: str | None) -> str:
    return html.escape(text or "", quote=True)


def sector_ytd_bars_svg(bars: list[YtdReturnBar], benchmark: float, ticker_ret: float) -> str:
    all_bars = [
        YtdReturnBar(symbol="YOU", label="Ticker", return_pct=ticker_ret),
        YtdReturnBar(symbol="SPY", label="SPY", return_pct=benchmark),
        *bars,
    ]
    max_abs = max(abs(b.return_pct) for b in all_bars) or 1
    max_abs = max(max_abs, 8)
    w, h = 320, 100
    n = len(all_bars)
    slot = (w - 20) / max(n, 1)
    bar_w = min(slot * 0.55, 44)
    parts = []
    for i, b in enumerate(all_bars):
        cx = 10 + slot * i + slot / 2
        height = abs(b.return_pct) / max_abs * 36
        y0 = 55
        color = "#3dd68c" if b.return_pct >= 0 else "#ff6b6b"
        if b.return_pct >= 0:
            rect = f'<rect x="{cx - bar_w/2:.1f}" y="{y0 - height:.1f}" width="{bar_w:.1f}" height="{height:.1f}" fill="{color}"/>'
        else:
            rect = f'<rect x="{cx - bar_w/2:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{height:.1f}" fill="{color}"/>'
        parts.append(rect)
        parts.append(
            f'<text x="{cx:.1f}" y="78" text-anchor="middle" font-family="monospace" '
            f'font-size="7" fill="#8a8478">{_esc(b.label)}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="92" text-anchor="middle" font-family="monospace" '
            f'font-size="8" fill="#f4f0e6">{b.return_pct:+.1f}%</text>'
        )
    parts.append(
        f'<line x1="8" y1="55" x2="{w-8}" y2="55" stroke="rgba(255,255,255,0.12)" stroke-width="0.5"/>'
    )
    return (
        f'<svg class="sector-bars-svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="YTD returns comparison">'
        f'{"".join(parts)}</svg>'
    )
