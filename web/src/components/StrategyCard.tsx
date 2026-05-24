import type { Strategy } from "../types";
import { MetricCell } from "./MetricCell";
import { PayoffChart } from "./PayoffChart";
import { FinancialDisclaimer } from "./FinancialDisclaimer";

type StrategyCardProps = {
  strategy: Strategy;
  index: number;
  expanded: boolean;
  onToggle: (index: number) => void;
  accentColor: string;
  showGreeks: boolean;
  spotPrice: number;
  compact?: boolean;
};

function money(value: number | "∞", prefix = ""): string {
  if (value === "∞") return "∞";
  const sign = value < 0 ? "-" : prefix;
  return `${sign}$${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function qualityColor(verdict?: string): string {
  if (verdict === "Tradeable") return "var(--positive)";
  if (verdict === "Avoid") return "var(--negative)";
  return "var(--accent)";
}

export function StrategyCard({
  strategy: s,
  index,
  expanded,
  onToggle,
  accentColor,
  showGreeks,
  spotPrice,
  compact = false,
}: StrategyCardProps) {
  const isTop = s.rank === 1;
  const padding = compact ? "14px 16px" : "20px 22px";
  const scenarios = s.scenarios ?? [];
  const managementRules = s.managementRules ?? [];
  const education = s.education ?? [];

  return (
    <div
      className="strategy-card"
      style={{
        background: "var(--bg-surface)",
        border: isTop ? `1px solid ${accentColor}33` : "1px solid var(--border)",
        borderRadius: 12,
        padding,
        marginBottom: compact ? 8 : 12,
        cursor: "pointer",
        minWidth: 0,
        transition: "border-color 0.3s, box-shadow 0.3s, background 0.3s",
        animation: `slideUp 0.6s var(--ease) ${0.6 + index * 0.15}s both`,
        position: "relative",
        boxShadow: isTop ? `0 0 40px ${accentColor}08` : "none",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = isTop
          ? `${accentColor}55`
          : "rgba(255,255,255,0.10)";
        e.currentTarget.style.background = "var(--bg-elevated)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = isTop
          ? `${accentColor}33`
          : "var(--border)";
        e.currentTarget.style.background = "var(--bg-surface)";
      }}
      onClick={() => onToggle(index)}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: compact ? 10 : 14,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontFamily: "var(--mono)",
            fontWeight: 500,
            flexShrink: 0,
            background: isTop ? `${accentColor}18` : "var(--bg-elevated)",
            color: isTop ? accentColor : "var(--text-2)",
            border: isTop
              ? `1px solid ${accentColor}30`
              : "1px solid var(--border)",
          }}
        >
          {s.rank}
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: "var(--serif)",
              fontSize: compact ? 18 : 20,
              fontWeight: 400,
              color: "var(--text-1)",
            }}
          >
            {s.name}
          </div>
          <div
            style={{
              fontSize: 11,
              fontFamily: "var(--mono)",
              color: "var(--text-3)",
              marginTop: 2,
            }}
          >
            {s.tag}
          </div>
          {s.tradeQuality && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                marginTop: 8,
                padding: "3px 8px",
                borderRadius: 999,
                background: `${qualityColor(s.tradeQuality.verdict)}18`,
                border: `1px solid ${qualityColor(s.tradeQuality.verdict)}33`,
                color: qualityColor(s.tradeQuality.verdict),
                fontSize: 10,
                fontFamily: "var(--mono)",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {s.tradeQuality.verdict} · {s.tradeQuality.score}
            </div>
          )}
        </div>
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontFamily: "var(--mono)",
              fontSize: 18,
              fontWeight: 500,
              color: accentColor,
            }}
          >
            {s.score}
          </div>
          <div
            style={{
              fontSize: 9,
              color: "var(--text-3)",
              fontFamily: "var(--mono)",
              letterSpacing: "0.04em",
            }}
          >
            SCORE
          </div>
        </div>
      </div>

      <div
        className="strategy-card-chart"
        onClick={(e) => e.stopPropagation()}
      >
        <PayoffChart
          data={s.payoffData}
          currentPrice={spotPrice}
          accentColor={accentColor}
          compact={compact}
        />
      </div>

      <div
        className={`strategy-card-metrics${compact ? " strategy-card-metrics--compact" : ""}`}
        style={{ marginBottom: expanded ? 16 : 0 }}
      >
        <MetricCell
          label="Max Gain"
          value={s.metrics.maxGain === "∞" ? "Unlimited" : money(s.metrics.maxGain, "+")}
          color="var(--positive)"
        />
        <MetricCell
          label="Max Loss"
          value={
            typeof s.metrics.maxLoss === "number"
              ? `-$${s.metrics.maxLoss}`
              : s.metrics.maxLoss
          }
          color="var(--negative)"
        />
        <MetricCell label="PoP" value={`${s.metrics.pop}%`} />
        <MetricCell
          label="Breakeven"
          value={s.metrics.breakevens.join(" / ")}
        />
        <MetricCell
          label="Exp. Value"
          value={`$${s.metrics.ev}`}
          color={accentColor}
        />
        <MetricCell label="Risk/Reward" value={s.metrics.riskReward} />
      </div>

      {s.warning && (
        <div
          style={{
            marginTop: 12,
            padding: "8px 12px",
            borderRadius: 8,
            background: "var(--negative-bg)",
            border: "1px solid rgba(196,83,74,0.15)",
            fontSize: 11.5,
            color: "#d4756d",
            lineHeight: 1.5,
          }}
        >
          ⚠ {s.warning}
        </div>
      )}

      {expanded && (
        <div style={{ marginTop: 16, animation: "fadeIn 0.3s ease" }}>
          {showGreeks && (
            <div
              style={{
                display: "flex",
                gap: 20,
                padding: "12px 0",
                borderTop: "1px solid var(--border)",
                marginBottom: 12,
              }}
            >
              {[
                { label: "Δ", value: s.greeks.delta.toFixed(2) },
                {
                  label: "Θ",
                  value:
                    (s.greeks.theta >= 0 ? "+" : "") + s.greeks.theta.toFixed(2),
                },
                { label: "V", value: s.greeks.vega.toFixed(2) },
                { label: "Γ", value: s.greeks.gamma.toFixed(3) },
              ].map((g) => (
                <div key={g.label} style={{ textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-3)",
                      fontFamily: "var(--serif)",
                      fontWeight: 500,
                      fontStyle: "italic",
                    }}
                  >
                    {g.label}
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      fontFamily: "var(--mono)",
                      color: "var(--text-1)",
                      marginTop: 2,
                    }}
                  >
                    {g.value}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div
            style={{
              padding: "12px 0",
              borderTop: "1px solid var(--border)",
            }}
          >
            <div
              style={{
                fontSize: 10,
                fontFamily: "var(--mono)",
                color: "var(--text-3)",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Legs
            </div>
            {s.legs.map((leg) => (
              <div
                key={leg.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginBottom: 6,
                  fontSize: 12.5,
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: 10,
                    padding: "2px 6px",
                    borderRadius: 4,
                    background:
                      leg.action === "BUY"
                        ? "var(--positive-bg)"
                        : "var(--negative-bg)",
                    color:
                      leg.action === "BUY"
                        ? "var(--positive)"
                        : "var(--negative)",
                    fontWeight: 500,
                  }}
                >
                  {leg.action} {leg.qty}×
                </span>
                <span style={{ color: "var(--text-1)", flex: 1 }}>
                  {leg.label}
                </span>
                <span
                  style={{ fontFamily: "var(--mono)", color: "var(--text-2)" }}
                >
                  ${leg.premium.toFixed(2)}
                </span>
              </div>
            ))}
          </div>

          <div
            style={{
              padding: "12px 0",
              borderTop: "1px solid var(--border)",
            }}
          >
            <div
              style={{
                fontSize: 10,
                fontFamily: "var(--mono)",
                color: "var(--text-3)",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Trade Quality
            </div>
            {s.tradeQuality && (
              <div style={{ marginBottom: 12 }}>
                <div
                  style={{
                    color: qualityColor(s.tradeQuality.verdict),
                    fontFamily: "var(--mono)",
                    fontSize: 12,
                    marginBottom: 6,
                  }}
                >
                  {s.tradeQuality.verdict} · score {s.tradeQuality.score}/100
                </div>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {s.tradeQuality.reasons.map((reason) => (
                    <li
                      key={reason}
                      style={{ color: "var(--text-2)", fontSize: 12, lineHeight: 1.55 }}
                    >
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div
              style={{
                fontSize: 10,
                fontFamily: "var(--mono)",
                color: "var(--text-3)",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              Critic Analysis
            </div>
            <p
              style={{
                fontSize: 12.5,
                color: "var(--text-2)",
                lineHeight: 1.65,
                margin: 0,
              }}
            >
              {s.critique}
            </p>
          </div>

          {(s.liquidity || scenarios.length > 0) && (
            <div
              style={{
                padding: "12px 0",
                borderTop: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontFamily: "var(--mono)",
                  color: "var(--text-3)",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  marginBottom: 8,
                }}
              >
                Accuracy Checks
              </div>
              {s.liquidity && (
                <div
                  style={{
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    marginBottom: 10,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      fontSize: 12,
                      color: "var(--text-2)",
                    }}
                  >
                    <span>Liquidity: {s.liquidity.label}</span>
                    <span style={{ fontFamily: "var(--mono)" }}>{s.liquidity.score}/100</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
                    {s.liquidity.quoteQuality}
                  </div>
                  {s.liquidity.spreadWarnings.map((w) => (
                    <div key={w} style={{ fontSize: 11, color: "var(--accent)", marginTop: 6 }}>
                      {w}
                    </div>
                  ))}
                </div>
              )}
              {scenarios.length > 0 && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
                    gap: 6,
                  }}
                >
                  {scenarios.map((scenario) => (
                    <div
                      key={scenario.label}
                      style={{
                        padding: "8px 6px",
                        borderRadius: 8,
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        textAlign: "center",
                      }}
                    >
                      <div style={{ fontSize: 10, color: "var(--text-3)" }}>
                        {scenario.label}
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--mono)",
                          fontSize: 11,
                          color: scenario.pnl >= 0 ? "var(--positive)" : "var(--negative)",
                          marginTop: 4,
                        }}
                      >
                        {money(scenario.pnl, "+")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {(managementRules.length > 0 || education.length > 0) && (
            <div
              style={{
                padding: "12px 0",
                borderTop: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontFamily: "var(--mono)",
                  color: "var(--text-3)",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  marginBottom: 8,
                }}
              >
                Manage This Trade
              </div>
              {managementRules.map((rule) => (
                <div key={rule.label} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: accentColor, fontFamily: "var(--mono)" }}>
                    {rule.label}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.5 }}>
                    {rule.detail}
                  </div>
                </div>
              ))}
              {education.length > 0 && (
                <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>
                  {education.map((point) => (
                    <li
                      key={point}
                      style={{ fontSize: 12, color: "var(--text-3)", lineHeight: 1.55 }}
                    >
                      {point}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {s.vsNext && (
            <div
              style={{
                marginTop: 4,
                padding: "10px 14px",
                borderRadius: 8,
                background: `${accentColor}08`,
                border: `1px solid ${accentColor}15`,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                style={{
                  fontSize: 10,
                  fontFamily: "var(--mono)",
                  color: accentColor,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                Why this beats #{s.rank + 1}
              </div>
              <p
                style={{
                  fontSize: 12,
                  color: "var(--text-2)",
                  lineHeight: 1.6,
                  margin: 0,
                }}
              >
                {s.vsNext}
              </p>
            </div>
          )}

          <div style={{ marginTop: 16 }}>
            <FinancialDisclaimer variant="inline" />
          </div>
        </div>
      )}
    </div>
  );
}

