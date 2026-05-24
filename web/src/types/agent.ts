// ---------------------------------------------------------------------------
// Agent SSE event types
// ---------------------------------------------------------------------------

export type AgentEventType =
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "reasoning"
  | "context"
  | "strategies"
  | "error"
  | "done";

export interface AgentEvent {
  type: AgentEventType;
  data: Record<string, unknown>;
  ts: number;
}

// Specific event data shapes

export interface ThinkingData {
  message: string;
  step: number;
}

export interface ToolCallData {
  tool: string;
  arguments: Record<string, unknown>;
  step: number;
}

export interface ToolResultData {
  tool: string;
  result: Record<string, unknown>;
  step: number;
}

export interface ReasoningData {
  message: string;
  step: number;
}

export interface ContextData {
  ticker: string;
  direction: string;
  magnitude?: string;
  horizon: string;
  risk_budget: string;
  agent_analysis?: string;
  get_iv_rank?: IVRankResult;
  get_upcoming_earnings?: EarningsResult;
  get_news_sentiment?: NewsSentimentResult;
  get_historical_post_earnings_move?: PostEarningsMoveResult;
  get_expected_move?: ExpectedMoveResult;
  calculate_magnitude?: MagnitudeResult;
  assess_structure_fit?: StructureFitResult;
}

export interface MagnitudeResult {
  ticker: string;
  magnitude: string;
  direction: string;
  horizon_days: number;
  expected_move_pct?: number;
  calibrated_move_pct?: number;
  method?: string;
  note?: string;
}

export interface IVRankResult {
  ticker: string;
  current_rv_30d: number;
  rv_252d_high: number;
  rv_252d_low: number;
  iv_rank: number;
  regime: "Low" | "Mid" | "High";
  note?: string;
  error?: string;
}

export interface EarningsResult {
  ticker: string;
  estimated_next_earnings: string | null;
  days_until_earnings: number | null;
  earnings_in_trade_window: boolean;
  recent_earnings_news: Array<{
    title: string;
    published: string;
    source: string;
  }>;
}

export interface NewsSentimentResult {
  ticker: string;
  overall_sentiment: "bullish" | "bearish" | "neutral";
  sentiment_score: number;
  headline_count: number;
  headlines: Array<{
    title: string;
    source: string;
    published: string;
    tone: string;
  }>;
}

export interface PostEarningsMoveResult {
  ticker: string;
  post_earnings_moves: Array<{
    date: string;
    gap_pct: number;
    day_move_pct: number;
    fwd_5d_pct: number | null;
  }>;
  median_absolute_move: number | null;
  count: number;
}

export interface ExpectedMoveResult {
  ticker: string;
  spot: number;
  dte: number;
  expected_move_pct: number;
  expected_move_dollar: number;
  method: string;
}

export interface StructureFitResult {
  direction: string;
  iv_regime: string;
  earnings_in_window: boolean;
  recommended_structures: Array<{
    structure: string;
    reason: string;
  }>;
  structures_to_avoid: Array<{
    structure: string;
    reason: string;
  }>;
}

// Discriminated union for typed event handling
export type TypedAgentEvent =
  | { type: "thinking"; data: ThinkingData }
  | { type: "tool_call"; data: ToolCallData }
  | { type: "tool_result"; data: ToolResultData }
  | { type: "reasoning"; data: ReasoningData }
  | { type: "context"; data: ContextData }
  | { type: "strategies"; data: { strategies: unknown[] } }
  | { type: "error"; data: { message: string } }
  | { type: "done"; data: { steps: number } };

// ---------------------------------------------------------------------------
// Request type (mirrors backend ThesisRequest)
// ---------------------------------------------------------------------------

export interface ThesisRequest {
  query: string;
  underlying?: string;
  direction?: string;
  magnitude?: string;
  horizon?: string;
  risk_budget?: string;
  confidence?: number;
  summary?: string;
}
