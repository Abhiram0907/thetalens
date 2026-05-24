import type { Leg } from "../types";

export type TimePayoffPoint = {
  day: number;
  pnl: number;
};

const SIGMA = 0.48;
const RATE = 0.0525;

function normCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const p =
    d *
    t *
    (0.3193815 +
      t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x >= 0 ? 1 - p : p;
}

function intrinsic(type: Leg["type"], S: number, K: number): number {
  return type === "PUT" ? Math.max(K - S, 0) : Math.max(S - K, 0);
}

/** Black–Scholes option mark (per share). */
export function optionMark(
  type: Leg["type"],
  S: number,
  K: number,
  dte: number,
  sigma = SIGMA,
  r = RATE,
): number {
  if (dte <= 0) return intrinsic(type, S, K);
  const T = dte / 365;
  const sqrtT = Math.sqrt(T);
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
  const d2 = d1 - sigma * sqrtT;

  if (type === "CALL") {
    return S * normCdf(d1) - K * Math.exp(-r * T) * normCdf(d2);
  }
  return K * Math.exp(-r * T) * normCdf(-d2) - S * normCdf(-d1);
}

/** Position P&L at `daysElapsed` with spot held at `spot` (fractional days allowed). */
export function strategyPnlAtDay(
  legs: Leg[],
  spot: number,
  daysElapsed: number,
): number {
  let pnl = 0;
  legs.forEach((leg) => {
    const sign = leg.action === "BUY" ? 1 : -1;
    const rem = Math.max(0, leg.dte - daysElapsed);
    const mark = optionMark(leg.type, spot, leg.strike, rem);
    pnl += sign * leg.qty * (mark - leg.premium) * 100;
  });
  return pnl;
}

export function maxStrategyDte(legs: Leg[]): number {
  return Math.max(...legs.map((l) => l.dte), 1);
}

/**
 * Dense P&L series for smooth drawing.
 * Samples every ~0.2 day plus exact leg expiry days to preserve real kinks.
 */
export function generateTimePayoffCurve(
  legs: Leg[],
  spot: number,
): TimePayoffPoint[] {
  const maxDay = maxStrategyDte(legs);
  const step = 0.2;
  const daySet = new Set<number>();

  for (let d = 0; d <= maxDay; d += step) {
    daySet.add(Math.round(d * 1000) / 1000);
  }
  daySet.add(0);
  daySet.add(maxDay);
  legs.forEach((leg) => {
    if (leg.dte <= maxDay) daySet.add(leg.dte);
    if (leg.dte > 0) daySet.add(leg.dte - 0.01);
  });

  const days = Array.from(daySet).sort((a, b) => a - b);
  return days.map((day) => ({
    day,
    pnl: strategyPnlAtDay(legs, spot, day),
  }));
}

export function formatDayLabel(day: number, maxDay: number): string {
  if (day <= 0) return "Today";
  if (day >= maxDay - 0.5) return "Expiry";
  if (day < 1) return `${Math.round(day * 10) / 10}d`;
  if (day < 7) return `${Math.round(day)}d`;
  const w = Math.round(day / 7);
  return w === 1 ? "1w" : `${w}w`;
}
