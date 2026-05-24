import type { ParsedView } from "../types";

type ViewSidebarProps = {
  view: ParsedView;
  accentColor: string;
};

export function ViewSidebar({ view, accentColor }: ViewSidebarProps) {
  const fields = [
    { label: "Direction", value: view.direction, icon: view.directionIcon },
    { label: "Magnitude", value: view.magnitude },
    { label: "Horizon", value: `${view.horizon} (${view.horizonLabel})` },
    { label: "Vol View", value: view.volatilityView },
    { label: "Risk Budget", value: view.riskBudget === "not specified" ? "No limit" : view.riskBudget },
  ];

  return (
    <div
      className="view-sidebar"
      style={{
        width: 260,
        flexShrink: 0,
        padding: "28px 24px",
        borderRight: "1px solid var(--border)",
        overflow: "auto",
        animation: "slideRight 0.7s var(--ease) both",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontFamily: "var(--mono)",
          color: "var(--text-3)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: 6,
        }}
      >
        Parsed View
      </div>
      <div
        className="view-sidebar-ticker"
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 10,
          marginBottom: 28,
        }}
      >
        <span
          style={{
            fontFamily: "var(--serif)",
            fontSize: 32,
            fontWeight: 300,
            color: accentColor,
          }}
        >
          {view.underlying}
        </span>
        <span
          style={{
            fontFamily: "var(--mono)",
            fontSize: 14,
            color: "var(--text-2)",
          }}
        >
          ${view.underlyingPrice}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 24,
          padding: "8px 12px",
          background: "var(--accent-dim)",
          borderRadius: 8,
        }}
      >
        <span
          style={{
            fontFamily: "var(--mono)",
            fontSize: 11,
            color: accentColor,
          }}
        >
          IV Rank
        </span>
        <span
          style={{
            fontFamily: "var(--mono)",
            fontSize: 13,
            color: "var(--text-1)",
            fontWeight: 500,
          }}
        >
          {view.ivRank}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-3)" }}>
          {view.ivLabel}
        </span>
      </div>

      <div className="view-sidebar-fields">
      {fields.map((f, i) => (
        <div
          key={f.label}
          className="view-sidebar-field"
          style={{
            marginBottom: 18,
            animation: `slideUp 0.5s var(--ease) ${0.3 + i * 0.08}s both`,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontFamily: "var(--mono)",
              color: "var(--text-3)",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            {f.label}
          </div>
          <div style={{ fontSize: 15, color: "var(--text-1)", fontWeight: 400 }}>
            {"icon" in f && f.icon && (
              <span style={{ color: "#c4534a", marginRight: 6 }}>{f.icon}</span>
            )}
            {f.value}
          </div>
        </div>
      ))}
      </div>
    </div>
  );
}
