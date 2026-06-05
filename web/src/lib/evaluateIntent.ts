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
