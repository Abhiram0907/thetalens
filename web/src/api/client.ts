import type { FollowUpQuestion } from "../lib/evaluateIntent";
import { API_BASE } from "../lib/apiBase";
import { userFacingApiError } from "../lib/safeErrors";
import type { DataProvenance, ParsedView, ReasoningStep, Strategy } from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiCapturedIntent = {
  underlying: string | null;
  direction: string | null;
  magnitude: string | null;
  horizon: string | null;
  risk_budget: string | null;
  mode: "thesis" | "scanner";
};

export type CapturedIntent = {
  underlying: string | null;
  direction: string | null;
  magnitude: string | null;
  horizon: string | null;
  riskBudget: string | null;
  mode: "thesis" | "scanner";
};

type ApiIntentResponse = {
  is_clear: boolean;
  confidence: number;
  captured: ApiCapturedIntent;
  missing: string[];
  questions: FollowUpQuestion[];
  summary: string;
  clarify_reasoning_steps: ApiReasoningStep[];
};

type ApiReasoningStep = {
  node: string;
  message: string;
  delay: number;
};

type ApiLeg = {
  action: "BUY" | "SELL";
  qty: number;
  type: "PUT" | "CALL";
  strike: number;
  dte: number;
  premium: number;
  label: string;
  back_month?: boolean;
};

type ApiStrategy = {
  rank: number;
  name: string;
  tag: string;
  legs: ApiLeg[];
  metrics: {
    max_gain: number | string;
    max_loss: number | string;
    breakevens: string[];
    pop: number;
    ev: number;
    risk_reward: string;
  };
  greeks: { delta: number; theta: number; vega: number; gamma: number };
  score: number;
  critique: string;
  vs_next: string | null;
  warning?: string;
  liquidity?: {
    score: number;
    label: string;
    quote_quality: string;
    spread_warnings: string[];
  } | null;
  trade_quality?: {
    verdict: "Tradeable" | "Caution" | "Avoid";
    score: number;
    reasons: string[];
  } | null;
  scenarios?: Array<{
    label: string;
    underlying_price: number;
    pnl: number;
  }>;
  management_rules?: Array<{
    label: string;
    detail: string;
  }>;
  education?: string[];
};

type ApiDataProvenance = {
  spot_source: "yfinance" | "polygon";
  spot_as_of: string | null;
  options_price_method: "black_scholes_modeled";
  vol_input: "realized_30d" | "implied" | "default";
  data_age_warning: string | null;
};

type ApiParsedView = {
  direction: string;
  direction_icon: string;
  magnitude: string;
  horizon: string;
  horizon_label: string;
  volatility_view: string;
  risk_budget: string;
  underlying: string;
  underlying_price: number;
  realized_vol_rank?: number;
  realized_vol_regime?: string;
  realized_vol_label?: string;
  iv_rank: number;
  iv_label: string;
};

type ApiAnalyzeResponse = {
  parsed_view: ApiParsedView;
  reasoning_steps: ApiReasoningStep[];
  strategies: ApiStrategy[];
  underlying_price: number;
  data_provenance: ApiDataProvenance;
};

export type IntentResult = {
  isClear: boolean;
  confidence: number;
  captured: CapturedIntent;
  missing: string[];
  questions: FollowUpQuestion[];
  summary: string;
  clarifyReasoningSteps: ReasoningStep[];
};

function mapCaptured(c: ApiCapturedIntent): CapturedIntent {
  return {
    underlying: c.underlying,
    direction: c.direction,
    magnitude: c.magnitude,
    horizon: c.horizon,
    riskBudget: c.risk_budget,
    mode: c.mode ?? "thesis",
  };
}

export type AnalyzeResult = {
  parsedView: ParsedView;
  reasoningSteps: ReasoningStep[];
  strategies: Omit<Strategy, "payoffData">[];
  underlyingPrice: number;
  dataProvenance: DataProvenance;
};

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const err = (await res.json()) as { detail?: string };
      if (typeof err.detail === "string") detail = err.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(userFacingApiError(res.status, detail), res.status);
  }

  return res.json() as Promise<T>;
}

function mapReasoning(steps: ApiReasoningStep[]): ReasoningStep[] {
  return steps.map((s) => ({
    node: s.node,
    message: s.message,
    delay: s.delay,
  }));
}

export function mapAgentBuildPayload(data: {
  parsed_view: ApiParsedView;
  reasoning_steps: ApiReasoningStep[];
  strategies: ApiStrategy[];
  underlying_price: number;
  data_provenance?: ApiDataProvenance;
}): AnalyzeResult {
  return {
    parsedView: mapParsedView(data.parsed_view),
    reasoningSteps: mapReasoning(data.reasoning_steps),
    strategies: data.strategies.map(mapStrategy),
    underlyingPrice: data.underlying_price,
    dataProvenance: mapDataProvenance(data.data_provenance),
  };
}

function mapDataProvenance(p?: ApiDataProvenance): DataProvenance {
  if (!p) {
    return {
      spotSource: "yfinance",
      spotAsOf: null,
      optionsPriceMethod: "black_scholes_modeled",
      volInput: "default",
      dataAgeWarning: null,
    };
  }
  return {
    spotSource: p.spot_source,
    spotAsOf: p.spot_as_of,
    optionsPriceMethod: p.options_price_method,
    volInput: p.vol_input,
    dataAgeWarning: p.data_age_warning,
  };
}

function mapParsedView(v: ApiParsedView): ParsedView {
  const realizedVolRank = v.realized_vol_rank ?? v.iv_rank;
  const realizedVolLabel = v.realized_vol_label ?? v.iv_label;
  return {
    direction: v.direction,
    directionIcon: v.direction_icon,
    magnitude: v.magnitude,
    horizon: v.horizon,
    horizonLabel: v.horizon_label,
    volatilityView: v.volatility_view,
    riskBudget: v.risk_budget,
    underlying: v.underlying,
    underlyingPrice: v.underlying_price,
    realizedVolRank,
    realizedVolRegime: v.realized_vol_regime ?? v.volatility_view,
    realizedVolLabel,
    ivRank: v.iv_rank ?? realizedVolRank,
    ivLabel: v.iv_label ?? realizedVolLabel,
  };
}

function mapStrategy(s: ApiStrategy): Omit<Strategy, "payoffData"> {
  return {
    rank: s.rank,
    name: s.name,
    tag: s.tag,
    legs: s.legs.map((leg) => ({
      action: leg.action,
      qty: leg.qty,
      type: leg.type,
      strike: leg.strike,
      dte: leg.dte,
      premium: leg.premium,
      label: leg.label,
      backMonth: leg.back_month,
    })),
    metrics: {
      maxGain: s.metrics.max_gain === "∞" ? "∞" : Number(s.metrics.max_gain),
      maxLoss: s.metrics.max_loss === "∞" ? "∞" : Number(s.metrics.max_loss),
      breakevens: s.metrics.breakevens,
      pop: s.metrics.pop,
      ev: s.metrics.ev,
      riskReward: s.metrics.risk_reward,
    },
    greeks: s.greeks,
    score: s.score,
    critique: s.critique,
    vsNext: s.vs_next,
    warning: s.warning,
    liquidity: s.liquidity
      ? {
          score: s.liquidity.score,
          label: s.liquidity.label,
          quoteQuality: s.liquidity.quote_quality,
          spreadWarnings: s.liquidity.spread_warnings,
        }
      : null,
    tradeQuality: s.trade_quality ?? null,
    scenarios: (s.scenarios ?? []).map((scenario) => ({
      label: scenario.label,
      underlyingPrice: scenario.underlying_price,
      pnl: scenario.pnl,
    })),
    managementRules: (s.management_rules ?? []).map((rule) => ({
      label: rule.label,
      detail: rule.detail,
    })),
    education: s.education ?? [],
  };
}

export async function fetchIntent(query: string): Promise<IntentResult> {
  const data = await postJson<ApiIntentResponse>("/api/intent", { query });
  return {
    isClear: data.is_clear,
    confidence: data.confidence,
    captured: mapCaptured(data.captured),
    missing: data.missing,
    questions: data.questions,
    summary: data.summary,
    clarifyReasoningSteps: mapReasoning(data.clarify_reasoning_steps),
  };
}

function capturedToApi(captured: CapturedIntent): ApiCapturedIntent {
  return {
    underlying: captured.underlying,
    direction: captured.direction,
    magnitude: captured.magnitude,
    horizon: captured.horizon,
    risk_budget: captured.riskBudget,
    mode: captured.mode,
  };
}

export async function fetchAnalyze(
  query: string,
  captured?: CapturedIntent | null,
): Promise<AnalyzeResult> {
  const body: { query: string; captured?: ApiCapturedIntent } = { query };
  if (captured) {
    body.captured = capturedToApi(captured);
  }
  const data = await postJson<ApiAnalyzeResponse>("/api/analyze", body);
  return {
    parsedView: mapParsedView(data.parsed_view),
    reasoningSteps: mapReasoning(data.reasoning_steps),
    strategies: data.strategies.map(mapStrategy),
    underlyingPrice: data.underlying_price,
    dataProvenance: mapDataProvenance(data.data_provenance),
  };
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export type ScannerStock = {
  ticker: string;
  name: string;
  sector: string;
  marketCapLabel: string;
  avgVolume: number;
  price: number;
  changePct: number;
  beta: number;
  realizedVol30d: number;
  correlation: number;
  ivRank: number | null;
  ivRvSpread: number | null;
  earningsWithin30d: boolean;
  earningsDate: string | null;
  opportunityScore: number;
};

export type SeedContext = {
  ticker: string;
  name: string;
  sector: string;
  marketCapLabel: string;
  price: number;
  changePct: number;
  betaSpy: number;
  realizedVol30d: number;
  ivRank: number | null;
};

type ApiScannerStock = {
  ticker: string;
  name: string;
  sector: string;
  market_cap_label: string;
  avg_volume: number;
  price: number;
  change_pct: number;
  beta: number;
  realized_vol_30d: number;
  correlation: number;
  iv_rank: number | null;
  iv_rv_spread: number | null;
  earnings_within_30d: boolean;
  earnings_date: string | null;
  opportunity_score: number;
};

type ApiSeedContext = {
  ticker: string;
  name: string;
  sector: string;
  market_cap_label: string;
  price: number;
  change_pct: number;
  beta_spy: number;
  realized_vol_30d: number;
  iv_rank: number | null;
};

type ApiScannerResponse = {
  seed: string;
  seed_context: ApiSeedContext;
  results: ApiScannerStock[];
};

export type ScannerResult = {
  seed: string;
  seedContext: SeedContext;
  results: ScannerStock[];
};

function mapSeedContext(s: ApiSeedContext): SeedContext {
  return {
    ticker: s.ticker,
    name: s.name,
    sector: s.sector,
    marketCapLabel: s.market_cap_label,
    price: s.price,
    changePct: s.change_pct,
    betaSpy: s.beta_spy,
    realizedVol30d: s.realized_vol_30d,
    ivRank: s.iv_rank,
  };
}

function mapScannerStock(s: ApiScannerStock): ScannerStock {
  return {
    ticker: s.ticker,
    name: s.name,
    sector: s.sector,
    marketCapLabel: s.market_cap_label,
    avgVolume: s.avg_volume,
    price: s.price,
    changePct: s.change_pct,
    beta: s.beta,
    realizedVol30d: s.realized_vol_30d,
    correlation: s.correlation,
    ivRank: s.iv_rank,
    ivRvSpread: s.iv_rv_spread,
    earningsWithin30d: s.earnings_within_30d,
    earningsDate: s.earnings_date,
    opportunityScore: s.opportunity_score,
  };
}

export async function fetchScanner(ticker: string): Promise<ScannerResult> {
  const data = await postJson<ApiScannerResponse>("/api/scanner", { ticker });
  return {
    seed: data.seed,
    seedContext: mapSeedContext(data.seed_context),
    results: data.results.map(mapScannerStock),
  };
}
