import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { AgentView } from "./components/agent";
import { AppShell } from "./components/AppShell";
import { FinancialDisclaimer } from "./components/FinancialDisclaimer";
import { ReasoningPanel } from "./components/ReasoningPanel";
import { DataProvenanceBanner } from "./components/DataProvenanceBanner";
import { StrategyCard } from "./components/StrategyCard";
import { ViewSidebar } from "./components/ViewSidebar";
import {
  ApiError,
  fetchAnalyze,
  fetchIntent,
  mapAgentBuildPayload,
  type CapturedIntent,
  type ScannerStock,
} from "./api/client";
import { ScannerView } from "./components/ScannerView";
import type { AgentBuildPayload } from "./hooks/useAgentStream";
import { DEMO_QUERY, VAGUE_DEMO_QUERY, SCANNER_DEMO_QUERY } from "./data/mockData";
import { enrichStrategies } from "./lib/enrichStrategies";
import { userFacingNetworkError } from "./lib/safeErrors";
import type { DataProvenance, ParsedView, ReasoningStep, Strategy } from "./types";

const ACCENT_COLOR = "#c9a655";
const PARSE_DELAY_MS = 700;

type Phase = "input" | "checking" | "researching" | "analyzing" | "complete" | "scanning";

export default function App() {
  const [phase, setPhase] = useState<Phase>("input");
  const [query, setQuery] = useState("");
  const [capturedIntent, setCapturedIntent] = useState<CapturedIntent | null>(
    null,
  );
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [visibleCards, setVisibleCards] = useState(0);
  const [expandedCard, setExpandedCard] = useState<number | null>(null);
  const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
  const [parsedView, setParsedView] = useState<ParsedView | null>(null);
  const [dataProvenance, setDataProvenance] = useState<DataProvenance | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const isInputFlow = phase === "input" || phase === "checking";
  const isResearching = phase === "researching";
  const isAnalysisLayout = phase === "analyzing" || phase === "complete";

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }, []);

  const schedule = useCallback((fn: () => void, delay: number) => {
    const tid = setTimeout(fn, delay);
    timersRef.current.push(tid);
  }, []);

  const streamReasoning = useCallback(
    (steps: ReasoningStep[], onDone?: () => void) => {
      setVisibleSteps(0);
      steps.forEach((step, i) => {
        schedule(() => setVisibleSteps(i + 1), step.delay + 400);
      });
      if (onDone) {
        const last = steps[steps.length - 1];
        schedule(onDone, (last?.delay ?? 0) + 800);
      }
    },
    [schedule],
  );

  const revealStrategies = useCallback(
    (items: Strategy[], steps: ReasoningStep[]) => {
      clearTimers();
      streamReasoning(steps);

      items.forEach((_, i) => {
        schedule(() => setVisibleCards(i + 1), 5000 + i * 600);
      });

      schedule(() => {
        setPhase("complete");
        setExpandedCard(0);
      }, 5000 + items.length * 600 + 400);
    },
    [clearTimers, schedule, streamReasoning],
  );

  const runAnalysis = useCallback(
    async (resolvedQuery: string) => {
      setQuery(resolvedQuery);
      setPhase("analyzing");
      setVisibleCards(0);
      setExpandedCard(null);
      setError(null);
      clearTimers();

      try {
        const result = await fetchAnalyze(resolvedQuery);
        const enriched = enrichStrategies(result.strategies, result.underlyingPrice);
        setParsedView(result.parsedView);
        setDataProvenance(result.dataProvenance);
        setStrategies(enriched);
        setReasoningSteps(result.reasoningSteps);
        revealStrategies(enriched, result.reasoningSteps);
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : userFacingNetworkError();
        setError(message);
        setPhase("input");
      }
    },
    [clearTimers, revealStrategies],
  );

  const beginIntentCheck = useCallback(
    async (rawQuery: string) => {
      const q = rawQuery.trim();
      if (!q) return;

      clearTimers();
      setPhase("checking");
      setVisibleSteps(0);
      setVisibleCards(0);
      setExpandedCard(null);
      setCapturedIntent(null);
      setError(null);

      await new Promise((r) => setTimeout(r, PARSE_DELAY_MS));

      try {
        const evaluation = await fetchIntent(q);

        setCapturedIntent(evaluation.captured);
        if (evaluation.captured.mode === "scanner") {
          setPhase("scanning");
        } else {
          setPhase("researching");
        }
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : userFacingNetworkError();
        setError(message);
        setPhase("input");
      }
    },
    [clearTimers],
  );

  const handleAgentComplete = useCallback(
    async (_context: Record<string, unknown>, buildPayload: AgentBuildPayload | null) => {
      setPhase("analyzing");
      setVisibleCards(0);
      setExpandedCard(null);
      setError(null);
      clearTimers();

      if (
        buildPayload?.parsed_view &&
        buildPayload.strategies &&
        buildPayload.strategies.length > 0
      ) {
        try {
          const result = mapAgentBuildPayload({
            parsed_view: buildPayload.parsed_view,
            reasoning_steps: buildPayload.reasoning_steps ?? [],
            strategies: buildPayload.strategies as Parameters<
              typeof mapAgentBuildPayload
            >[0]["strategies"],
            underlying_price: buildPayload.underlying_price ?? buildPayload.parsed_view.underlying_price,
            data_provenance: buildPayload.data_provenance,
          });
          const enriched = enrichStrategies(result.strategies, result.underlyingPrice);
          setParsedView(result.parsedView);
          setDataProvenance(result.dataProvenance);
          setStrategies(enriched);
          setReasoningSteps(result.reasoningSteps);
          revealStrategies(enriched, result.reasoningSteps);
          return;
        } catch {
          /* fall through to legacy analyze */
        }
      }

      await runAnalysis(query);
    },
    [clearTimers, query, revealStrategies, runAnalysis],
  );

  const handleScannerBuild = useCallback(
    (ticker: string, stock: ScannerStock) => {
      const ivr = stock.ivRank;
      const inferredDirection =
        ivr != null && ivr >= 65
          ? "Neutral"
          : stock.beta > 1.3
            ? "Bullish"
            : null;
      const magnitude =
        stock.realizedVol30d > 50
          ? "large"
          : stock.realizedVol30d > 25
            ? "moderate"
            : "small";
      const hint = [
        `IV rank ${ivr?.toFixed(0) ?? "unknown"}`,
        `beta ${stock.beta.toFixed(2)}`,
        `RVol ${stock.realizedVol30d.toFixed(1)}%`,
        stock.earningsWithin30d
          ? `earnings ${stock.earningsDate}`
          : null,
      ]
        .filter(Boolean)
        .join(", ");

      setQuery(`${ticker} — ${hint}`);
      setCapturedIntent({
        underlying: ticker,
        direction: inferredDirection,
        magnitude,
        horizon: "60 days",
        riskBudget: null,
        mode: "thesis",
      });
      setPhase("researching");
    },
    [],
  );

  const handleSubmit = () => void beginIntentCheck(query);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const useExample = (text: string) => {
    setQuery(text);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
  };

  const toggleCard = (idx: number) => {
    setExpandedCard((prev) => (prev === idx ? null : idx));
  };

  const resetToInput = () => {
    clearTimers();
    setPhase("input");
    setQuery("");
    setVisibleSteps(0);
    setVisibleCards(0);
    setExpandedCard(null);
    setCapturedIntent(null);
    setReasoningSteps([]);
    setParsedView(null);
    setDataProvenance(null);
    setStrategies([]);
    setError(null);
  };

  if (isInputFlow) {
    return (
      <AppShell>
      <div className="input-phase">
        <div
          className="input-phase-glow"
          style={{
            position: "absolute",
            top: "18%",
            left: "50%",
            transform: "translateX(-50%)",
            width: 500,
            height: 500,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${ACCENT_COLOR}06 0%, transparent 70%)`,
            pointerEvents: "none",
          }}
        />

        <div className="input-phase-container">
          <div
            style={{
              textAlign: "center",
              marginBottom: 48,
              animation: "fadeIn 1s var(--ease) 0.1s both",
            }}
          >
            <div
              className="input-phase-logo"
              style={{
                fontFamily: "var(--serif)",
                fontSize: 72,
                fontWeight: 300,
                color: ACCENT_COLOR,
                lineHeight: 1,
                marginBottom: 8,
              }}
            >
              θ
            </div>
            <div
              className="input-phase-title"
              style={{
                fontFamily: "var(--serif)",
                fontSize: 28,
                fontWeight: 300,
                color: "var(--text-1)",
                letterSpacing: "0.12em",
              }}
            >
              thetalens
            </div>
            <div
              style={{
                fontFamily: "var(--sans)",
                fontSize: 12,
                color: "var(--text-3)",
                marginTop: 8,
                letterSpacing: "0.04em",
              }}
            >
              Options structuring intelligence
            </div>
            <div style={{ marginTop: 12 }}>
              <FinancialDisclaimer variant="inline" />
            </div>
          </div>

          <div style={{ animation: "slideUp 0.8s var(--ease) 0.3s both" }}>
            {error && (
              <div
                style={{
                  marginBottom: 16,
                  padding: "12px 14px",
                  borderRadius: 8,
                  background: "rgba(212, 137, 107, 0.12)",
                  border: "1px solid rgba(212, 137, 107, 0.35)",
                  fontSize: 12,
                  color: "var(--text-2)",
                  lineHeight: 1.5,
                }}
              >
                {error}
              </div>
            )}
            <textarea
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your view…"
              readOnly={phase === "checking"}
              style={{
                ...inputPhaseStyles.textarea,
                opacity: phase === "checking" ? 0.7 : 1,
              }}
              rows={3}
            />

            {phase === "checking" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 10,
                  marginTop: 16,
                }}
              >
                <div
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: ACCENT_COLOR,
                    animation: "pulse 1.2s ease infinite",
                  }}
                />
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: "var(--mono)",
                    color: "var(--text-3)",
                  }}
                >
                  Extracting intent…
                </span>
              </div>
            )}

            <div
              style={{
                display: "flex",
                justifyContent: "center",
                marginTop: 20,
              }}
            >
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!query.trim() || phase === "checking"}
                style={{
                  ...inputPhaseStyles.button,
                  background:
                    query.trim() && phase !== "checking"
                      ? ACCENT_COLOR
                      : "var(--bg-elevated)",
                  color:
                    query.trim() && phase !== "checking"
                      ? "#080808"
                      : "var(--text-3)",
                  cursor:
                    query.trim() && phase !== "checking"
                      ? "pointer"
                      : "default",
                }}
              >
                Structure
              </button>
            </div>

          </div>

          {phase === "input" && (
          <div
            style={{
              animation: "fadeIn 1s var(--ease) 0.8s both",
              marginTop: 40,
              textAlign: "center",
            }}
          >
            <div
              style={{
                fontSize: 10,
                fontFamily: "var(--mono)",
                color: "var(--text-4)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                marginBottom: 10,
              }}
            >
              Examples
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 8,
              }}
            >
              <button
                type="button"
                onClick={() => useExample(DEMO_QUERY)}
                style={inputPhaseStyles.exampleBtn}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--text-2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-3)";
                }}
              >
                Clear view — NVDA bearish, 3 weeks, &lt;$500 risk
              </button>
              <button
                type="button"
                onClick={() => useExample(VAGUE_DEMO_QUERY)}
                style={inputPhaseStyles.exampleBtn}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--text-2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-3)";
                }}
              >
                Vague view — agent infers direction
              </button>
              <button
                type="button"
                onClick={() => useExample(SCANNER_DEMO_QUERY)}
                style={inputPhaseStyles.exampleBtn}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--text-2)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-3)";
                }}
              >
                Scanner — find stocks that move like NBIS
              </button>
            </div>
          </div>
          )}
        </div>
      </div>
      </AppShell>
    );
  }

  if (isResearching) {
    return (
      <AppShell>
      <div className="agent-phase-wrapper">
        <header className="agent-phase-header">
          <button
            type="button"
            onClick={resetToInput}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
            }}
            aria-label="New view"
          >
            <span
              style={{
                fontFamily: "var(--serif)",
                fontSize: 24,
                fontWeight: 300,
                color: ACCENT_COLOR,
              }}
            >
              θ
            </span>
            <span
              style={{
                fontFamily: "var(--serif)",
                fontSize: 16,
                fontWeight: 400,
                color: "var(--text-1)",
                letterSpacing: "0.08em",
              }}
            >
              thetalens
            </span>
          </button>
          <span
            style={{
              fontSize: 11,
              fontFamily: "var(--mono)",
              color: "var(--text-3)",
            }}
          >
            Research phase
          </span>
        </header>
        <div className="agent-phase-body">
          <AgentView
            parsedIntent={{
              underlying: capturedIntent?.underlying ?? undefined,
              direction: capturedIntent?.direction?.toLowerCase(),
              horizon: capturedIntent?.horizon ?? undefined,
              risk_budget: capturedIntent?.riskBudget ?? undefined,
              query,
            }}
            onComplete={handleAgentComplete}
            onBack={resetToInput}
            accentColor={ACCENT_COLOR}
          />
        </div>
      </div>
      </AppShell>
    );
  }

  if (phase === "scanning") {
    return (
      <AppShell>
      <div className="agent-phase-wrapper">
        <header className="agent-phase-header">
          <button
            type="button"
            onClick={resetToInput}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
            }}
            aria-label="New view"
          >
            <span
              style={{
                fontFamily: "var(--serif)",
                fontSize: 24,
                fontWeight: 300,
                color: ACCENT_COLOR,
              }}
            >
              θ
            </span>
            <span
              style={{
                fontFamily: "var(--serif)",
                fontSize: 16,
                fontWeight: 400,
                color: "var(--text-1)",
                letterSpacing: "0.08em",
              }}
            >
              thetalens
            </span>
          </button>
          <span
            style={{
              fontSize: 11,
              fontFamily: "var(--mono)",
              color: "var(--text-3)",
            }}
          >
            Scanner mode
          </span>
        </header>
        <div className="agent-phase-body">
          <ScannerView
            seedTicker={capturedIntent?.underlying ?? "SPY"}
            onBuildStrategies={handleScannerBuild}
            onBack={resetToInput}
            accentColor={ACCENT_COLOR}
          />
        </div>
      </div>
      </AppShell>
    );
  }

  if (!isAnalysisLayout) {
    return null;
  }

  return (
    <AppShell>
    <div className="analysis-wrapper">
      <header className="analysis-header" style={analysisStyles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            type="button"
            onClick={resetToInput}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
            }}
            aria-label="New view"
          >
            <span
              style={{
                fontFamily: "var(--serif)",
                fontSize: 24,
                fontWeight: 300,
                color: ACCENT_COLOR,
              }}
            >
              θ
            </span>
            <span
              style={{
                fontFamily: "var(--serif)",
                fontSize: 16,
                fontWeight: 400,
                color: "var(--text-1)",
                letterSpacing: "0.08em",
              }}
            >
              thetalens
            </span>
          </button>
        </div>
        <div
          className="analysis-header-meta"
          style={{ display: "flex", alignItems: "center", gap: 16 }}
        >
          {phase === "analyzing" && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: ACCENT_COLOR,
                  animation: "pulse 1.2s ease infinite",
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontFamily: "var(--mono)",
                  color: "var(--text-3)",
                }}
              >
                Structuring…
              </span>
            </div>
          )}
          {phase === "complete" && (
            <span
              style={{
                fontSize: 11,
                fontFamily: "var(--mono)",
                color: "var(--positive)",
                letterSpacing: "0.04em",
              }}
            >
              ✓ Complete
            </span>
          )}
          {(phase === "analyzing" || phase === "complete") && parsedView && (
            <div
              style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--text-2)" }}
            >
              {parsedView.underlying}{" "}
              <span style={{ color: "var(--text-3)" }}>
                ${parsedView.underlyingPrice}
              </span>
            </div>
          )}
        </div>
      </header>

      <div className="analysis-body">
        {parsedView && (
          <ViewSidebar view={parsedView} accentColor={ACCENT_COLOR} />
        )}

        <div className="analysis-center">
          <div
            className="analysis-center-inner"
            style={{
              maxWidth: 640,
              margin: "0 auto",
              padding: "28px 0",
            }}
          >
            {(phase === "analyzing" || phase === "complete") && (
              <>
                <div
                  className="desktop-only"
                  style={{
                    marginBottom: 24,
                    padding: "14px 18px",
                    borderRadius: 10,
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border)",
                    animation: "fadeIn 0.5s var(--ease) 0.3s both",
                  }}
                >
                  <div
                    style={{
                      fontSize: 10,
                      fontFamily: "var(--mono)",
                      color: "var(--text-3)",
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      marginBottom: 6,
                    }}
                  >
                    Your View
                  </div>
                  <p
                    style={{
                      fontSize: 13,
                      color: "var(--text-2)",
                      lineHeight: 1.55,
                      margin: 0,
                      fontStyle: "italic",
                    }}
                  >
                    &ldquo;{query}&rdquo;
                  </p>
                </div>

                {dataProvenance && (phase === "analyzing" || phase === "complete") && (
                  <div
                    style={{
                      animation: "fadeIn 0.5s var(--ease) both",
                      marginBottom: 16,
                    }}
                  >
                    <DataProvenanceBanner provenance={dataProvenance} />
                  </div>
                )}

                {visibleCards > 0 && (
                  <div
                    style={{
                      animation: "fadeIn 0.5s var(--ease) both",
                      marginBottom: 16,
                    }}
                  >
                    <FinancialDisclaimer variant="banner" />
                    <div
                      style={{
                        fontFamily: "var(--serif)",
                        fontSize: 22,
                        fontWeight: 300,
                        color: "var(--text-1)",
                        marginTop: 16,
                      }}
                    >
                      Ranked Structures
                    </div>
                    <div
                      style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}
                    >
                      {visibleCards} of {strategies.length} · sorted by thesis
                      rank (execution quality on each card)
                    </div>
                  </div>
                )}

                {strategies.slice(0, visibleCards).map((s, i) => (
                  <StrategyCard
                    key={s.rank}
                    strategy={s}
                    index={i}
                    expanded={expandedCard === i}
                    onToggle={toggleCard}
                    accentColor={ACCENT_COLOR}
                    showGreeks
                    spotPrice={parsedView?.underlyingPrice ?? 0}
                    dataProvenance={dataProvenance}
                  />
                ))}

                {phase === "analyzing" && visibleCards < strategies.length && (
                  <div
                    style={{
                      height: 120,
                      borderRadius: 12,
                      marginTop: 8,
                      background:
                        "linear-gradient(90deg, var(--bg-surface) 0%, var(--bg-elevated) 50%, var(--bg-surface) 100%)",
                      backgroundSize: "200% 100%",
                      animation: "shimmer 2s ease infinite",
                    }}
                  />
                )}
              </>
            )}
          </div>
        </div>

        <ReasoningPanel steps={reasoningSteps} visibleCount={visibleSteps} />
      </div>
    </div>
    </AppShell>
  );
}

const inputPhaseStyles: Record<string, CSSProperties> = {
  textarea: {
    width: "100%",
    padding: "18px 20px",
    fontSize: 15,
    fontFamily: "var(--sans)",
    color: "var(--text-1)",
    background: "var(--bg-surface)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    resize: "none",
    outline: "none",
    lineHeight: 1.6,
    transition: "border-color 0.3s",
  },
  button: {
    padding: "10px 36px",
    fontSize: 13,
    fontFamily: "var(--sans)",
    fontWeight: 500,
    border: "none",
    borderRadius: 8,
    letterSpacing: "0.04em",
    transition: "all 0.3s",
  },
  exampleBtn: {
    background: "none",
    border: "none",
    color: "var(--text-3)",
    fontSize: 12,
    fontFamily: "var(--sans)",
    cursor: "pointer",
    padding: "6px 12px",
    borderRadius: 6,
    transition: "color 0.3s",
  },
};

const analysisStyles: Record<string, CSSProperties> = {
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    height: 56,
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
};
