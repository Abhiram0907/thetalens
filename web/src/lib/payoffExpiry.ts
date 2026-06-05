import type { Leg, PayoffPoint } from "../types";

export function computeExpiryPayoff(
  legs: Leg[],
  center: number,
  halfRange: number,
  opts: { atFrontExpiry?: boolean } = {},
): PayoffPoint[] {
  const n = 120;
  const lo = center - halfRange;
  const hi = center + halfRange;
  const pts: PayoffPoint[] = [];

  for (let i = 0; i <= n; i++) {
    const S = lo + (hi - lo) * (i / n);
    let pnl = 0;

    legs.forEach((leg) => {
      const sign = leg.action === "BUY" ? 1 : -1;
      const intr =
        leg.type === "PUT"
          ? Math.max(leg.strike - S, 0)
          : Math.max(S - leg.strike, 0);

      if (leg.backMonth && opts.atFrontExpiry) {
        const sigma = center * 0.48 * Math.sqrt(21 / 365);
        const d = (S - leg.strike) / sigma;
        const tv = leg.premium * 0.52 * Math.exp(-0.5 * d * d);
        const val = intr + Math.max(tv, 0);
        pnl += sign * leg.qty * (val - leg.premium) * 100;
      } else {
        pnl += sign * leg.qty * (intr - leg.premium) * 100;
      }
    });

    pts.push({ price: +S.toFixed(2), pnl: Math.round(pnl) });
  }
  return pts;
}

export function findBreakevens(data: PayoffPoint[]): number[] {
  const out: number[] = [];
  for (let i = 0; i < data.length - 1; i++) {
    const a = data[i];
    const b = data[i + 1];
    if (a.pnl === 0) out.push(a.price);
    if ((a.pnl >= 0 && b.pnl < 0) || (a.pnl < 0 && b.pnl >= 0)) {
      const t = a.pnl / (a.pnl - b.pnl);
      out.push(+(a.price + t * (b.price - a.price)).toFixed(2));
    }
  }
  const last = data[data.length - 1];
  if (last.pnl === 0) out.push(last.price);
  return [...new Set(out.map((p) => +p.toFixed(2)))];
}

function niceStep(range: number, targetTicks = 6): number {
  if (range <= 0) return 1;
  const raw = range / targetTicks;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  if (norm <= 1.5) return mag;
  if (norm <= 3.5) return 2 * mag;
  if (norm <= 7.5) return 5 * mag;
  return 10 * mag;
}

export function buildTicks(min: number, max: number, targetTicks = 6): number[] {
  const step = niceStep(max - min, targetTicks);
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.01; v += step) {
    ticks.push(+v.toFixed(2));
  }
  return ticks;
}

export function formatPriceTick(v: number): string {
  if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  return `$${Number.isInteger(v) ? v : v.toFixed(2)}`;
}

export function formatPnlTick(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(1)}k`;
  return `${sign}$${abs}`;
}

export function pnlAtPrice(data: PayoffPoint[], price: number): number {
  if (!data.length) return 0;
  if (price <= data[0].price) return data[0].pnl;
  if (price >= data[data.length - 1].price) return data[data.length - 1].pnl;
  for (let i = 0; i < data.length - 1; i++) {
    const a = data[i];
    const b = data[i + 1];
    if (price >= a.price && price <= b.price) {
      const t = (price - a.price) / (b.price - a.price);
      return Math.round(a.pnl + t * (b.pnl - a.pnl));
    }
  }
  return data[data.length - 1].pnl;
}
