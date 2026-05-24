import { useCallback, useState } from "react";
import { useAgentStream, type AgentBuildPayload } from "../../hooks/useAgentStream";
import { ReasoningTrace } from "./ReasoningTrace";
import { IVRankBadge } from "./IVRankBadge";
import { FinancialDisclaimer } from "../FinancialDisclaimer";
import type { ThesisRequest } from "../../types/agent";
import "./ReasoningTrace.css";
import "./AgentView.css";

interface AgentViewProps {
  parsedIntent?: {
    underlying?: string;
    direction?: string;
    horizon?: string;
    risk_budget?: string;
    query?: string;
  };
  onComplete?: (
    context: Record<string, unknown>,
    buildPayload: AgentBuildPayload | null,
  ) => void;
  onBack?: () => void;
  apiBase?: string;
  accentColor?: string;
}

function normalizeDirection(direction?: string): string {
  return (direction ?? "").toLowerCase();
}

export function AgentView({
  parsedIntent,
  onComplete,
  onBack,
  apiBase = "",
  accentColor = "var(--accent)",
}: AgentViewProps) {
  const agent = useAgentStream(apiBase);
  const [hasStarted, setHasStarted] = useState(false);

  const handleStart = useCallback(() => {
    if (!parsedIntent?.query) return;
    setHasStarted(true);

    const request: ThesisRequest = {
      query: parsedIntent.query,
      underlying: parsedIntent.underlying ?? undefined,
      direction: parsedIntent.direction ?? undefined,
      horizon: parsedIntent.horizon ?? undefined,
      risk_budget: parsedIntent.risk_budget ?? undefined,
    };

    agent.start(request);
  }, [parsedIntent, agent]);

  const handleProceed = useCallback(() => {
    if (agent.context && onComplete) {
      onComplete(
        agent.context as unknown as Record<string, unknown>,
        agent.buildPayload,
      );
    }
  }, [agent.context, agent.buildPayload, onComplete]);

  const ivRank = agent.context?.get_iv_rank;
  const dir = normalizeDirection(parsedIntent?.direction);
  const calculatedMagnitude =
    agent.context?.magnitude ??
    agent.context?.calculate_magnitude?.magnitude;

  return (
    <div className="agent-view">
      <div className="agent-view__sidebar">
        <div className="agent-sidebar-card">
          <h3 className="agent-sidebar-title">Trade Thesis</h3>
          {parsedIntent && (
            <div className="agent-thesis-fields">
              <div className="agent-thesis-field">
                <span className="agent-field-label">Underlying</span>
                <span className="agent-field-value agent-field-ticker">
                  {parsedIntent.underlying ?? "—"}
                </span>
              </div>
              <div className="agent-thesis-field">
                <span className="agent-field-label">Direction</span>
                <span className={`agent-field-value agent-direction-${dir || "neutral"}`}>
                  {dir === "bullish" && "↑ "}
                  {dir === "bearish" && "↓ "}
                  {parsedIntent.direction ?? "—"}
                </span>
              </div>
              <div className="agent-thesis-field">
                <span className="agent-field-label">Horizon</span>
                <span className="agent-field-value">{parsedIntent.horizon ?? "—"}</span>
              </div>
              <div className="agent-thesis-field">
                <span className="agent-field-label">Risk Budget</span>
                <span className="agent-field-value">{parsedIntent.risk_budget ?? "—"}</span>
              </div>

              {calculatedMagnitude && (
                <div className="agent-thesis-field agent-thesis-field--full">
                  <span className="agent-field-label">Calculated Magnitude</span>
                  <span className="agent-field-value" style={{ color: "var(--accent)" }}>
                    {calculatedMagnitude}
                  </span>
                </div>
              )}

              {ivRank && !ivRank.error && (
                <div className="agent-thesis-field agent-thesis-field--full">
                  <IVRankBadge
                    rank={ivRank.iv_rank}
                    regime={ivRank.regime}
                    rv={ivRank.current_rv_30d}
                  />
                </div>
              )}
            </div>
          )}

          {agent.context?.get_upcoming_earnings?.earnings_in_trade_window && (
            <div className="agent-earnings-alert">
              <span className="agent-earnings-alert-icon">⚠</span>
              <span>
                Earnings estimated{" "}
                <strong>{agent.context.get_upcoming_earnings.estimated_next_earnings}</strong>
                {" "}— falls within trade window
              </span>
            </div>
          )}

          {agent.context?.get_news_sentiment && (
            <div className="agent-sentiment-row">
              <span className="agent-field-label">News Sentiment</span>
              <span
                className={`agent-sentiment-tag agent-sentiment-${agent.context.get_news_sentiment.overall_sentiment}`}
              >
                {agent.context.get_news_sentiment.overall_sentiment}
              </span>
            </div>
          )}

          {agent.context?.get_expected_move && (
            <div className="agent-expected-move">
              <span className="agent-field-label">Expected Move</span>
              <span className="agent-field-value">
                ±{agent.context.get_expected_move.expected_move_pct}%
                {" "}(${agent.context.get_expected_move.expected_move_dollar})
              </span>
            </div>
          )}
        </div>

        <div className="agent-sidebar-actions">
          {!hasStarted && (
            <button
              type="button"
              className="agent-btn agent-btn--primary"
              onClick={handleStart}
              style={{ background: accentColor }}
            >
              Run Research Agent
            </button>
          )}
          {!agent.isStreaming && agent.context && (
            <button type="button" className="agent-btn agent-btn--primary" onClick={handleProceed} style={{ background: accentColor }}>
              Build Strategies →
            </button>
          )}
          {agent.isStreaming && (
            <button type="button" className="agent-btn agent-btn--secondary" onClick={agent.stop}>
              Stop
            </button>
          )}
          {onBack && (
            <button
              type="button"
              className="agent-btn agent-btn--ghost"
              onClick={() => {
                agent.reset();
                onBack();
              }}
            >
              ← Back
            </button>
          )}
        </div>

        {agent.error && (
          <div className="agent-earnings-alert" style={{ marginTop: 0 }}>
            {agent.error}
          </div>
        )}
      </div>

      <div className="agent-view__main">
        {!hasStarted ? (
          <div className="agent-empty-state">
            <div className="agent-empty-icon">θ</div>
            <h2>Trade Thesis Agent</h2>
            <p>
              ThetaLens researches your thesis before suggesting structures — IV rank,
              earnings catalysts, news sentiment, and expected move — then calculates
              magnitude from market data and filters structures to fit the vol regime.
            </p>
            <FinancialDisclaimer variant="banner" />
            <button
              type="button"
              className="agent-btn agent-btn--primary agent-btn--lg"
              onClick={handleStart}
              style={{ background: accentColor }}
            >
              Start Research
            </button>
          </div>
        ) : (
          <ReasoningTrace
            events={agent.events}
            isStreaming={agent.isStreaming}
            currentStep={agent.currentStep}
          />
        )}
      </div>
    </div>
  );
}
