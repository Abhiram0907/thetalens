import type { ParsedView } from "../types";
import "./ViewSidebar.css";

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
    {
      label: "Risk Budget",
      value: view.riskBudget === "not specified" ? "No limit" : view.riskBudget,
    },
  ];

  const riskLabel =
    view.riskBudget === "not specified" ? "No limit" : view.riskBudget;

  return (
    <div className="view-sidebar">
      <div className="view-sidebar-compact">
        <div className="view-sidebar-compact__row">
          <span className="view-sidebar-compact__ticker" style={{ color: accentColor }}>
            {view.underlying}
          </span>
          <span className="view-sidebar-compact__price">${view.underlyingPrice}</span>
          <span className="view-sidebar-compact__iv" style={{ color: accentColor }}>
            RV {view.realizedVolRank} · {view.realizedVolRegime}
          </span>
        </div>
        <div className="view-sidebar-compact__meta">
          <span className="view-sidebar-compact__chip">
            <span className="view-sidebar-compact__chip-label">Dir</span>
            <span style={{ color: "#c4534a" }}>{view.directionIcon}</span> {view.direction}
          </span>
          <span className="view-sidebar-compact__chip">
            <span className="view-sidebar-compact__chip-label">Move</span>
            {view.magnitude}
          </span>
          <span className="view-sidebar-compact__chip">
            <span className="view-sidebar-compact__chip-label">Horizon</span>
            {view.horizon}
          </span>
          <span className="view-sidebar-compact__chip">
            <span className="view-sidebar-compact__chip-label">Vol</span>
            {view.volatilityView}
          </span>
          <span className="view-sidebar-compact__chip">
            <span className="view-sidebar-compact__chip-label">Risk</span>
            {riskLabel}
          </span>
        </div>
      </div>

      <div className="view-sidebar-full">
        <div className="view-sidebar-label">Parsed View</div>
        <div className="view-sidebar-ticker">
          <span className="view-sidebar-ticker-symbol" style={{ color: accentColor }}>
            {view.underlying}
          </span>
          <span className="view-sidebar-ticker-price">${view.underlyingPrice}</span>
        </div>

        <div className="view-sidebar-iv">
          <span className="view-sidebar-iv-label" style={{ color: accentColor }}>
            Realized vol rank
          </span>
          <span className="view-sidebar-iv-value">{view.realizedVolRank}</span>
          <span className="view-sidebar-iv-regime">{view.realizedVolRegime}</span>
          <span
            className="view-sidebar-iv-regime"
            style={{ display: "block", marginTop: 4, fontSize: 10, lineHeight: 1.4 }}
          >
            {view.realizedVolLabel}
          </span>
        </div>

        <div className="view-sidebar-fields">
          {fields.map((f, i) => (
            <div
              key={f.label}
              className="view-sidebar-field"
              style={{
                animation: `slideUp 0.5s var(--ease) ${0.3 + i * 0.08}s both`,
              }}
            >
              <div className="view-sidebar-field-label">{f.label}</div>
              <div className="view-sidebar-field-value">
                {"icon" in f && f.icon && (
                  <span className="view-sidebar-field-icon">{f.icon}</span>
                )}
                {f.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
