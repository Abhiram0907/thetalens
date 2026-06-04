import type { CapturedIntent } from "../api/client";
import type { DataProvenance, ParsedView, ReasoningStep, Strategy } from "../types";

function mapParsedViewToApi(v: ParsedView) {
  return {
    direction: v.direction,
    direction_icon: v.directionIcon,
    magnitude: v.magnitude,
    horizon: v.horizon,
    horizon_label: v.horizonLabel,
    volatility_view: v.volatilityView,
    risk_budget: v.riskBudget,
    underlying: v.underlying,
    underlying_price: v.underlyingPrice,
    realized_vol_rank: v.realizedVolRank,
    realized_vol_regime: v.realizedVolRegime,
    realized_vol_label: v.realizedVolLabel,
    iv_rank: v.ivRank,
    iv_label: v.ivLabel,
  };
}

function mapProvenanceToApi(p: DataProvenance) {
  return {
    spot_source: p.spotSource,
    spot_as_of: p.spotAsOf,
    options_price_method: p.optionsPriceMethod,
    vol_input: p.volInput,
    data_age_warning: p.dataAgeWarning,
  };
}

function mapStrategyToApi(s: Strategy) {
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
      back_month: leg.backMonth,
    })),
    metrics: {
      max_gain: s.metrics.maxGain,
      max_loss: s.metrics.maxLoss,
      breakevens: s.metrics.breakevens,
      pop: s.metrics.pop,
      ev: s.metrics.ev,
      risk_reward: s.metrics.riskReward,
    },
    greeks: s.greeks,
    score: s.score,
    critique: s.critique,
    vs_next: s.vsNext,
    warning: s.warning,
    liquidity: s.liquidity
      ? {
          score: s.liquidity.score,
          label: s.liquidity.label,
          quote_quality: s.liquidity.quoteQuality,
          spread_warnings: s.liquidity.spreadWarnings,
        }
      : null,
    trade_quality: s.tradeQuality
      ? {
          verdict: s.tradeQuality.verdict,
          score: s.tradeQuality.score,
          reasons: s.tradeQuality.reasons,
        }
      : null,
    scenarios: (s.scenarios ?? []).map((x) => ({
      label: x.label,
      underlying_price: x.underlyingPrice,
      pnl: x.pnl,
    })),
    management_rules: (s.managementRules ?? []).map((x) => ({
      label: x.label,
      detail: x.detail,
    })),
    education: s.education ?? [],
  };
}

export type ExportPayloadInput = {
  query: string;
  captured?: CapturedIntent | null;
  parsedView: ParsedView;
  reasoningSteps: ReasoningStep[];
  strategies: Strategy[];
  underlyingPrice: number;
  dataProvenance: DataProvenance;
  researchReport?: Record<string, unknown> | null;
  enrichedContext?: Record<string, unknown> | null;
};

export function buildExportRequestBody(
  input: ExportPayloadInput,
  format: "html" | "json",
) {
  const captured = input.captured
    ? {
        underlying: input.captured.underlying,
        direction: input.captured.direction,
        magnitude: input.captured.magnitude,
        horizon: input.captured.horizon,
        risk_budget: input.captured.riskBudget,
        mode: input.captured.mode,
      }
    : null;

  return {
    format,
    query: input.query,
    captured,
    parsed_view: mapParsedViewToApi(input.parsedView),
    reasoning_steps: input.reasoningSteps.map((s) => ({
      node: s.node,
      message: s.message,
      delay: s.delay,
    })),
    strategies: input.strategies.map(mapStrategyToApi),
    underlying_price: input.underlyingPrice,
    data_provenance: mapProvenanceToApi(input.dataProvenance),
    enriched_context: input.enrichedContext ?? null,
    research_report: input.researchReport ?? null,
  };
}
