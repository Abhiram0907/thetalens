export type LegAction = "BUY" | "SELL";
export type OptionType = "PUT" | "CALL";

export type Leg = {
  action: LegAction;
  qty: number;
  type: OptionType;
  strike: number;
  dte: number;
  premium: number;
  label: string;
  backMonth?: boolean;
};

export type PayoffPoint = { price: number; pnl: number };

export type Strategy = {
  rank: number;
  name: string;
  tag: string;
  legs: Leg[];
  metrics: {
    maxGain: number | "∞";
    maxLoss: number | "∞";
    breakevens: string[];
    pop: number;
    ev: number;
    riskReward: string;
  };
  greeks: { delta: number; theta: number; vega: number; gamma: number };
  score: number;
  critique: string;
  vsNext: string | null;
  warning?: string;
  liquidity?: {
    score: number;
    label: string;
    quoteQuality: string;
    spreadWarnings: string[];
  } | null;
  tradeQuality?: {
    verdict: "Tradeable" | "Caution" | "Avoid";
    score: number;
    reasons: string[];
  } | null;
  scenarios?: {
    label: string;
    underlyingPrice: number;
    pnl: number;
  }[];
  managementRules?: {
    label: string;
    detail: string;
  }[];
  education?: string[];
  payoffData: PayoffPoint[];
};

export type DataProvenance = {
  spotSource: "yfinance" | "polygon";
  spotAsOf: string | null;
  optionsPriceMethod: "black_scholes_modeled";
  volInput: "realized_30d" | "implied" | "default";
  dataAgeWarning: string | null;
};

export type ParsedView = {
  direction: string;
  directionIcon: string;
  magnitude: string;
  horizon: string;
  horizonLabel: string;
  volatilityView: string;
  riskBudget: string;
  underlying: string;
  underlyingPrice: number;
  realizedVolRank: number;
  realizedVolRegime: string;
  realizedVolLabel: string;
  /** @deprecated Use realizedVolRank — kept for backward compatibility */
  ivRank: number;
  /** @deprecated Use realizedVolLabel */
  ivLabel: string;
};

export type ReasoningStep = {
  node: string;
  message: string;
  delay: number;
};