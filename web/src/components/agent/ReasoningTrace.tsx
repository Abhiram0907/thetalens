import { useEffect, useRef } from "react";
import { MarkdownContent } from "../MarkdownContent";
import type { TypedAgentEvent } from "../../types/agent";

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

const TOOL_ICONS: Record<string, string> = {
  get_iv_rank: "📊",
  get_upcoming_earnings: "📅",
  get_news_sentiment: "📰",
  get_historical_post_earnings_move: "📈",
  get_expected_move: "🎯",
  calculate_magnitude: "📐",
  assess_structure_fit: "🧩",
};

const TOOL_LABELS: Record<string, string> = {
  get_iv_rank: "Realized Vol Rank",
  get_upcoming_earnings: "Earnings Check",
  get_news_sentiment: "News Sentiment",
  get_historical_post_earnings_move: "Post-Earnings History",
  get_expected_move: "Expected Move",
  calculate_magnitude: "Magnitude Calculation",
  assess_structure_fit: "Structure Assessment",
};

function ThinkingBubble({ message }: { message: string }) {
  return (
    <div className="rt-event rt-thinking">
      <div className="rt-event-icon">💭</div>
      <div className="rt-event-body">
        <div className="rt-event-label">Thinking</div>
        <div className="rt-event-content">
          <MarkdownContent content={message} />
        </div>
      </div>
    </div>
  );
}

function ToolCallBubble({ tool, args }: { tool: string; args: Record<string, unknown> }) {
  const icon = TOOL_ICONS[tool] ?? "🔧";
  const label = TOOL_LABELS[tool] ?? tool;
  return (
    <div className="rt-event rt-tool-call">
      <div className="rt-event-icon">{icon}</div>
      <div className="rt-event-body">
        <div className="rt-event-label">{label}</div>
        <div className="rt-event-args">
          {Object.entries(args).map(([k, v]) => (
            <span key={k} className="rt-arg-chip">
              {k}: {String(v)}
            </span>
          ))}
        </div>
      </div>
      <div className="rt-spinner" />
    </div>
  );
}

function ToolResultBubble({ tool, result }: { tool: string; result: Record<string, unknown> }) {
  const icon = TOOL_ICONS[tool] ?? "✅";
  const label = TOOL_LABELS[tool] ?? tool;

  // Extract key metrics to display
  const highlights = extractHighlights(tool, result);

  return (
    <div className="rt-event rt-tool-result">
      <div className="rt-event-icon">{icon}</div>
      <div className="rt-event-body">
        <div className="rt-event-label">{label} — complete</div>
        {highlights.length > 0 && (
          <div className="rt-highlights">
            {highlights.map((h, i) => (
              <div key={i} className="rt-highlight">
                <span className="rt-highlight-key">{h.label}</span>
                <span className={`rt-highlight-value ${h.color ?? ""}`}>{h.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ReasoningBubble({ message }: { message: string }) {
  return (
    <div className="rt-event rt-reasoning">
      <div className="rt-event-icon">🧠</div>
      <div className="rt-event-body">
        <div className="rt-event-label">Analysis</div>
        <div className="rt-event-content rt-reasoning-text">
          <MarkdownContent content={message} />
        </div>
      </div>
    </div>
  );
}

function ErrorBubble({ message }: { message: string }) {
  return (
    <div className="rt-event rt-error">
      <div className="rt-event-icon">⚠️</div>
      <div className="rt-event-body">
        <div className="rt-event-content">{message}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Highlight extraction
// ---------------------------------------------------------------------------

interface Highlight {
  label: string;
  value: string;
  color?: string;
}

function extractHighlights(tool: string, result: Record<string, unknown>): Highlight[] {
  const h: Highlight[] = [];

  if (tool === "get_iv_rank") {
    const regime = String(result.regime ?? "");
    const rank = Number(result.iv_rank ?? 0);
    h.push({
      label: "RV Rank",
      value: `${rank}`,
      color: regime === "High" ? "rt-red" : regime === "Low" ? "rt-green" : "rt-yellow",
    });
    h.push({ label: "Regime", value: regime });
    h.push({ label: "30d RV", value: `${result.current_rv_30d ?? "—"}%` });
  }

  if (tool === "get_upcoming_earnings") {
    const date = String(result.estimated_next_earnings ?? "None found");
    const inWindow = result.earnings_in_trade_window;
    h.push({ label: "Next Earnings", value: date === "null" ? "Unknown" : date });
    h.push({
      label: "In Trade Window",
      value: inWindow ? "Yes ⚠️" : "No",
      color: inWindow ? "rt-red" : "rt-green",
    });
    if (result.days_until_earnings != null) {
      h.push({ label: "Days Until", value: String(result.days_until_earnings) });
    }
  }

  if (tool === "get_news_sentiment") {
    const sentiment = String(result.overall_sentiment ?? "neutral");
    const score = Number(result.sentiment_score ?? 0);
    h.push({
      label: "Sentiment",
      value: sentiment.charAt(0).toUpperCase() + sentiment.slice(1),
      color: sentiment === "bullish" ? "rt-green" : sentiment === "bearish" ? "rt-red" : "rt-yellow",
    });
    h.push({ label: "Score", value: `${score > 0 ? "+" : ""}${score}` });
    h.push({ label: "Articles", value: String(result.headline_count ?? 0) });
  }

  if (tool === "get_historical_post_earnings_move") {
    const median = result.median_absolute_move;
    h.push({
      label: "Median Move",
      value: median != null ? `±${median}%` : "—",
    });
    h.push({ label: "Quarters", value: String(result.count ?? 0) });
  }

  if (tool === "get_expected_move") {
    h.push({ label: "Spot", value: `$${result.spot ?? "—"}` });
    h.push({ label: "Expected Move", value: `±${result.expected_move_pct ?? "—"}%` });
    h.push({ label: "Dollar Move", value: `±$${result.expected_move_dollar ?? "—"}` });
  }

  if (tool === "calculate_magnitude") {
    h.push({
      label: "Magnitude",
      value: String(result.magnitude ?? "—"),
      color: "rt-yellow",
    });
    if (result.calibrated_move_pct != null) {
      h.push({
        label: "Calibrated",
        value: `±${result.calibrated_move_pct}%`,
      });
    }
    if (result.method) {
      const method = String(result.method).replace(/_/g, " ");
      h.push({ label: "Method", value: method });
    }
  }

  if (tool === "assess_structure_fit") {
    const rec = result.recommended_structures as Array<{ structure: string }> | undefined;
    const avoid = result.structures_to_avoid as Array<{ structure: string }> | undefined;
    if (rec?.length) {
      h.push({ label: "Recommended", value: rec.map((r) => r.structure).join(", "), color: "rt-green" });
    }
    if (avoid?.length) {
      h.push({ label: "Avoid", value: avoid.map((a) => a.structure).join(", "), color: "rt-red" });
    }
  }

  return h;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ReasoningTraceProps {
  events: TypedAgentEvent[];
  isStreaming: boolean;
  currentStep: number;
}

export function ReasoningTrace({ events, isStreaming, currentStep }: ReasoningTraceProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0 && !isStreaming) return null;

  return (
    <div className="reasoning-trace">
      <div className="rt-header">
        <span className="rt-header-icon">🔬</span>
        <span className="rt-header-title">Research Agent</span>
        {isStreaming && (
          <span className="rt-header-status">
            <span className="rt-pulse" />
            Step {currentStep + 1}
          </span>
        )}
      </div>
      <div className="rt-events">
        {events.map((event, i) => {
          switch (event.type) {
            case "thinking":
              return <ThinkingBubble key={i} message={event.data.message} />;
            case "tool_call":
              return <ToolCallBubble key={i} tool={event.data.tool} args={event.data.arguments} />;
            case "tool_result":
              return <ToolResultBubble key={i} tool={event.data.tool} result={event.data.result} />;
            case "reasoning":
              return <ReasoningBubble key={i} message={event.data.message} />;
            case "error":
              return <ErrorBubble key={i} message={event.data.message} />;
            case "done":
              return (
                <div key={i} className="rt-event rt-done">
                  <div className="rt-event-icon">✓</div>
                  <div className="rt-event-body">
                    <div className="rt-event-content">
                      Research complete — {event.data.steps} steps
                    </div>
                  </div>
                </div>
              );
            default:
              return null;
          }
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
