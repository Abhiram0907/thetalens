import { computeExpiryPayoff } from "./payoffExpiry";
import type { Leg, Strategy } from "../types";

function payoffHalfRange(
  strategy: Omit<Strategy, "payoffData">,
  underlyingPrice: number,
): number {
  const strikes = strategy.legs.map((leg) => leg.strike);
  const minStrike = Math.min(...strikes, underlyingPrice);
  const maxStrike = Math.max(...strikes, underlyingPrice);
  const structuralRange = Math.max(
    Math.abs(underlyingPrice - minStrike),
    Math.abs(maxStrike - underlyingPrice),
  );

  const tag = strategy.tag.toLowerCase();
  const isLongDated = strategy.legs.some((leg) => leg.dte >= 90);
  const hasCall = strategy.legs.some((leg) => leg.type === "CALL");
  const targetUpside = hasCall ? underlyingPrice * (isLongDated ? 0.32 : 0.22) : 0;
  const targetDownside = underlyingPrice * (isLongDated ? 0.22 : 0.16);
  const tagPadding =
    tag.includes("strangle") || tag.includes("ratio") ? underlyingPrice * 0.28 : 0;

  return Math.max(
    structuralRange * 1.45,
    targetUpside,
    targetDownside,
    tagPadding,
    underlyingPrice * 0.16,
    18,
  );
}

export function enrichStrategies(
  defs: Omit<Strategy, "payoffData">[],
  underlyingPrice: number,
): Strategy[] {
  return defs.map((s) => {
    const isMultiExpiry = s.tag === "diagonal" || s.tag === "calendar";
    return {
      ...s,
      payoffData: computeExpiryPayoff(
        s.legs as Leg[],
        underlyingPrice,
        payoffHalfRange(s, underlyingPrice),
        { atFrontExpiry: isMultiExpiry },
      ),
    };
  });
}
