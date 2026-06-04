import type { CapturedIntent } from "../api/client";
import type { DataProvenance, ParsedView, ReasoningStep, Strategy } from "../types";

const STORAGE_KEY = "thetalens:analysis-session";
const VERSION = 1;

export type PersistedPhase = "complete" | "scanning" | "researching";

export type AnalysisSession = {
  version: number;
  phase: PersistedPhase;
  query: string;
  capturedIntent: CapturedIntent | null;
  reasoningSteps: ReasoningStep[];
  parsedView: ParsedView | null;
  dataProvenance: DataProvenance | null;
  strategies: Strategy[];
  researchReport: Record<string, unknown> | null;
  expandedCard: number | null;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function parseSession(raw: string): AnalysisSession | null {
  try {
    const data = JSON.parse(raw) as unknown;
    if (!isRecord(data) || data.version !== VERSION) return null;
    if (typeof data.phase !== "string" || typeof data.query !== "string") {
      return null;
    }
    if (!["complete", "scanning", "researching"].includes(data.phase)) {
      return null;
    }
    if (data.phase === "complete") {
      if (!isRecord(data.parsedView) || !Array.isArray(data.strategies)) {
        return null;
      }
      if (data.strategies.length === 0) return null;
    }
    if (data.phase === "scanning") {
      const intent = data.capturedIntent;
      if (!isRecord(intent) || typeof intent.underlying !== "string") {
        return null;
      }
    }
    return data as AnalysisSession;
  } catch {
    return null;
  }
}

export function loadAnalysisSession(): AnalysisSession | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  return parseSession(raw);
}

export function saveAnalysisSession(session: Omit<AnalysisSession, "version">): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...session, version: VERSION }),
    );
  } catch {
    /* quota / private mode */
  }
}

export function clearAnalysisSession(): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
}

export type RestoredUiState = {
  phase: PersistedPhase;
  query: string;
  capturedIntent: CapturedIntent | null;
  reasoningSteps: ReasoningStep[];
  parsedView: ParsedView | null;
  dataProvenance: DataProvenance | null;
  strategies: Strategy[];
  researchReport: Record<string, unknown> | null;
  expandedCard: number | null;
  visibleSteps: number;
  visibleCards: number;
};

export function restoreUiState(session: AnalysisSession): RestoredUiState {
  const steps = session.reasoningSteps ?? [];
  const cards = session.strategies ?? [];
  const isComplete = session.phase === "complete";

  return {
    phase: session.phase,
    query: session.query,
    capturedIntent: session.capturedIntent,
    reasoningSteps: steps,
    parsedView: session.parsedView,
    dataProvenance: session.dataProvenance,
    strategies: cards,
    researchReport: session.researchReport,
    expandedCard: session.expandedCard ?? (isComplete && cards.length ? 0 : null),
    visibleSteps: isComplete ? steps.length : 0,
    visibleCards: isComplete ? cards.length : 0,
  };
}
