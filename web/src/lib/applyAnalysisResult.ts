import type { AnalyzeResult } from "../api/client";
import { enrichStrategies } from "./enrichStrategies";
import type { DataProvenance, ParsedView, ReasoningStep, Strategy } from "../types";

type AnalysisResultSetters = {
  setParsedView: (view: ParsedView) => void;
  setDataProvenance: (provenance: DataProvenance) => void;
  setStrategies: (strategies: Strategy[]) => void;
  setReasoningSteps: (steps: ReasoningStep[]) => void;
  setResearchReport?: (report: Record<string, unknown> | null) => void;
};

export function applyAnalysisResult(
  result: AnalyzeResult,
  setters: AnalysisResultSetters,
  revealStrategies: (items: Strategy[], steps: ReasoningStep[]) => void,
  researchReport?: Record<string, unknown> | null,
): Strategy[] {
  const enriched = enrichStrategies(result.strategies, result.underlyingPrice);
  setters.setParsedView(result.parsedView);
  setters.setDataProvenance(result.dataProvenance);
  setters.setStrategies(enriched);
  setters.setReasoningSteps(result.reasoningSteps);
  setters.setResearchReport?.(researchReport ?? null);
  revealStrategies(enriched, result.reasoningSteps);
  return enriched;
}
