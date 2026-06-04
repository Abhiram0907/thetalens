/** Types shared with API intent responses (client uses POST /api/intent). */

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
