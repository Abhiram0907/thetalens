import { computeExpiryPayoff } from "../lib/payoffExpiry";
import type { ParsedView, ReasoningStep, Strategy } from "../types";

export const CURRENT_PRICE = 135.42;

export const DEMO_QUERY =
  "NVDA bearish over the next 3 weeks — max risk $500";

export const VAGUE_DEMO_QUERY = "NVDA might move soon, not sure which way";

export const SCANNER_DEMO_QUERY = "Stocks that move like NBIS";

export const PARSED_VIEW: ParsedView = {
  direction: "Bearish",
  directionIcon: "↓",
  magnitude: "-5% to -10%",
  horizon: "21 days",
  horizonLabel: "3 weeks",
  volatilityView: "Neutral",
  riskBudget: "$500",
  underlying: "NVDA",
  underlyingPrice: 135.42,
  realizedVolRank: 42,
  realizedVolRegime: "Mid",
  realizedVolLabel: "42nd percentile · 30d realized vol (not options IV)",
  ivRank: 42,
  ivLabel: "42nd percentile · 30d realized vol (not options IV)",
};

export const NODE_COLORS: Record<string, string> = {
  "View Parser": "#6b9fd4",
  "Strategy Planner": "#c9a655",
  Pricer: "#5a9e78",
  Critic: "#d4896b",
  Synthesizer: "#dbb963",
};

export const REASONING_STEPS: ReasoningStep[] = [
  { node: "View Parser", message: "Parsing natural language view…", delay: 200 },
  {
    node: "View Parser",
    message: "Extracted: Bearish · -5% to -10% · 21-day horizon",
    delay: 900,
  },
  {
    node: "View Parser",
    message:
      "Vol view: Neutral (no explicit opinion) · Budget: $500 · Underlying: NVDA @ $135.42",
    delay: 1500,
  },
  {
    node: "Strategy Planner",
    message: "Generating candidate structures for moderate bearish view…",
    delay: 2400,
  },
  {
    node: "Strategy Planner",
    message:
      "IV Rank check: NVDA IV30 at 42nd pctl — short-vol structures permitted, not preferred",
    delay: 3100,
  },
  {
    node: "Strategy Planner",
    message:
      "Emitting 5 candidates: Bear Put Spread, Put Diagonal, BWB, Put Calendar, 1×2 Ratio Put",
    delay: 3800,
  },
  {
    node: "Pricer",
    message: "Fetching NVDA chain — Jun 01 / Jun 22 expiries…",
    delay: 4600,
  },
  {
    node: "Pricer",
    message: "Chain loaded: 28 strikes · bid-ask within 8% of mid — all liquid",
    delay: 5200,
  },
  {
    node: "Pricer",
    message: "Computing Greeks via Black-Scholes: σ = 0.48, r = 5.25%, S = 135.42",
    delay: 5700,
  },
  {
    node: "Pricer",
    message:
      "Monte Carlo: 10 000 GBM paths, 21-day horizon — simulating P&L distributions",
    delay: 6200,
  },
  {
    node: "Critic",
    message: "Ranking on EV / MaxLoss, theta efficiency, probability of profit…",
    delay: 7100,
  },
  {
    node: "Critic",
    message: "⚠ 1×2 Ratio Put: undefined max loss — violates $500 risk budget",
    delay: 7700,
  },
  {
    node: "Critic",
    message: "Bear Put Spread ranked #1: best EV/risk ($42.50 EV on $490 risk)",
    delay: 8300,
  },
  {
    node: "Synthesizer",
    message: "Playbook complete — 4 of 5 structures satisfy all constraints",
    delay: 9000,
  },
];

const STRATEGY_DEFS: Omit<Strategy, "payoffData">[] = [
  {
    rank: 1,
    name: "Bear Put Spread",
    tag: "vertical",
    legs: [
      {
        action: "BUY",
        qty: 1,
        type: "PUT",
        strike: 135,
        dte: 21,
        premium: 6.4,
        label: "Jun 01 135P",
      },
      {
        action: "SELL",
        qty: 1,
        type: "PUT",
        strike: 125,
        dte: 21,
        premium: 1.5,
        label: "Jun 01 125P",
      },
    ],
    metrics: {
      maxGain: 510,
      maxLoss: 490,
      breakevens: ["130.10"],
      pop: 38,
      ev: 42.5,
      riskReward: "1.04",
    },
    greeks: { delta: -0.28, theta: -2.15, vega: 0.18, gamma: 0.012 },
    score: 87,
    critique:
      "Optimal risk/reward for a -5% to -10% move. Defined risk fits $500 budget with $10 margin. Highest expected value among candidates at $42.50. Negative theta is acceptable given 21-day horizon — position profits before decay accelerates.",
    vsNext:
      "Beats Put Diagonal on expected value ($42.50 vs $38.20) and directional sensitivity (Δ -0.28 vs -0.22). Trades positive theta for better payoff in target zone.",
  },
  {
    rank: 2,
    name: "Put Diagonal",
    tag: "diagonal",
    legs: [
      {
        action: "BUY",
        qty: 1,
        type: "PUT",
        strike: 130,
        dte: 42,
        premium: 5.2,
        label: "Jun 22 130P",
        backMonth: true,
      },
      {
        action: "SELL",
        qty: 1,
        type: "PUT",
        strike: 125,
        dte: 21,
        premium: 1.0,
        label: "Jun 01 125P",
      },
    ],
    metrics: {
      maxGain: 680,
      maxLoss: 420,
      breakevens: ["128.80"],
      pop: 42,
      ev: 38.2,
      riskReward: "1.62",
    },
    greeks: { delta: -0.22, theta: 1.4, vega: 0.32, gamma: 0.008 },
    score: 82,
    critique:
      "Positive theta earns $1.40/day while position works. Higher PoP at 42%. Better for a gradual bleed than a sharp drop. Back-month long leg retains residual value if thesis takes longer than expected.",
    vsNext:
      "Beats BWB on probability of profit (42% vs 35%) and theta profile (+$1.40 vs +$0.85). Simpler to manage — single adjustment point vs three legs.",
  },
  {
    rank: 3,
    name: "Broken-Wing Butterfly",
    tag: "butterfly",
    legs: [
      {
        action: "BUY",
        qty: 1,
        type: "PUT",
        strike: 135,
        dte: 21,
        premium: 6.4,
        label: "Jun 01 135P",
      },
      {
        action: "SELL",
        qty: 2,
        type: "PUT",
        strike: 128,
        dte: 21,
        premium: 2.8,
        label: "Jun 01 128P",
      },
      {
        action: "BUY",
        qty: 1,
        type: "PUT",
        strike: 124,
        dte: 21,
        premium: 1.15,
        label: "Jun 01 124P",
      },
    ],
    metrics: {
      maxGain: 705,
      maxLoss: 195,
      breakevens: ["134.05", "124.95"],
      pop: 35,
      ev: 31.6,
      riskReward: "3.62",
    },
    greeks: { delta: -0.15, theta: 0.85, vega: 0.12, gamma: 0.015 },
    score: 76,
    critique:
      "Best risk/reward ratio (3.62) and lowest max loss ($195). Ideal if NVDA settles near $128. Positive theta. Narrow profit zone limits probability. Dual breakevens require precise targeting.",
    vsNext:
      "Beats Put Calendar on max gain ($705 vs $340) and risk/reward (3.62 vs 0.74). Narrower sweet spot but dramatically better payoff when correct.",
  },
  {
    rank: 4,
    name: "Put Calendar Spread",
    tag: "calendar",
    legs: [
      {
        action: "SELL",
        qty: 1,
        type: "PUT",
        strike: 130,
        dte: 21,
        premium: 3.8,
        label: "Jun 01 130P",
      },
      {
        action: "BUY",
        qty: 1,
        type: "PUT",
        strike: 130,
        dte: 42,
        premium: 5.2,
        label: "Jun 22 130P",
        backMonth: true,
      },
    ],
    metrics: {
      maxGain: 340,
      maxLoss: 140,
      breakevens: ["126.40", "133.80"],
      pop: 48,
      ev: 22.8,
      riskReward: "2.43",
    },
    greeks: { delta: -0.08, theta: 3.2, vega: 0.45, gamma: 0.003 },
    score: 68,
    critique:
      "Highest PoP (48%) and best theta ($3.20/day). Conservative, income-oriented play. Weak directional exposure (Δ -0.08) means limited gain if thesis is correct. Best for range-bound near $130.",
    vsNext:
      "Beats Ratio Put on risk profile — defined max loss ($140) vs unlimited. Higher PoP (48% vs 33%). Lower EV but no tail risk. Safer for risk-constrained accounts.",
  },
  {
    rank: 5,
    name: "1×2 Ratio Put Spread",
    tag: "ratio",
    legs: [
      {
        action: "BUY",
        qty: 1,
        type: "PUT",
        strike: 135,
        dte: 21,
        premium: 6.4,
        label: "Jun 01 135P",
      },
      {
        action: "SELL",
        qty: 2,
        type: "PUT",
        strike: 125,
        dte: 21,
        premium: 1.5,
        label: "Jun 01 125P",
      },
    ],
    metrics: {
      maxGain: 660,
      maxLoss: "∞",
      breakevens: ["134.60", "115.40"],
      pop: 33,
      ev: 28.4,
      riskReward: "N/A",
    },
    greeks: { delta: -0.35, theta: 0.5, vega: -0.08, gamma: 0.018 },
    score: 52,
    warning: "Undefined max loss below $115.40 violates $500 risk budget",
    critique:
      "Near-zero cost entry with strong directional exposure. However, the naked short put creates unlimited downside risk below $115.40, violating the stated risk budget. Included for comparison only.",
    vsNext: null,
  },
];

export const STRATEGIES: Strategy[] = STRATEGY_DEFS.map((s) => {
  const isMultiExpiry = s.tag === "diagonal" || s.tag === "calendar";
  return {
    ...s,
    payoffData: computeExpiryPayoff(s.legs, CURRENT_PRICE, 18, {
      atFrontExpiry: isMultiExpiry,
    }),
  };
});
