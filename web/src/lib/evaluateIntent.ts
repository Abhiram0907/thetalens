export type FollowUpField =
  | "underlying"
  | "direction"
  | "horizon"
  | "riskBudget";

export type FollowUpQuestion = {
  id: FollowUpField;
  label: string;
  prompt: string;
  type: "select" | "text";
  options?: { value: string; label: string }[];
  placeholder?: string;
};

export type IntentEvaluation = {
  isClear: boolean;
  confidence: number;
  missing: FollowUpField[];
  questions: FollowUpQuestion[];
  summary: string;
};

/** Client-side fallback — production flow uses POST /api/intent. */
export function evaluateIntent(query: string): IntentEvaluation {
  const q = query.trim();

  return {
    isClear: true,
    confidence: q.length < 24 ? 70 : 90,
    missing: [],
    questions: [],
    summary:
      "Intent retrieved; the agent will infer direction and fill gaps from market data.",
  };
}
