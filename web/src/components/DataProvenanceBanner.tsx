import type { DataProvenance } from "../types";

type DataProvenanceBannerProps = {
  provenance: DataProvenance;
  compact?: boolean;
};

function formatSpotAsOf(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return null;
  }
}

function volInputLabel(vol: DataProvenance["volInput"]): string {
  if (vol === "realized_30d") return "30-day realized vol";
  if (vol === "implied") return "implied vol";
  return "default estimate";
}

export function DataProvenanceBanner({
  provenance: p,
  compact = false,
}: DataProvenanceBannerProps) {
  const calibrated = formatSpotAsOf(p.spotAsOf);
  const spotSource =
    p.spotSource === "polygon" ? "Polygon prior close" : "Yahoo Finance prior close";

  return (
    <div
      role="note"
      style={{
        padding: compact ? "8px 12px" : "10px 14px",
        borderRadius: 8,
        background: "rgba(201, 166, 85, 0.08)",
        border: "1px solid rgba(201, 166, 85, 0.22)",
        fontSize: compact ? 11 : 12,
        lineHeight: 1.5,
        color: "var(--text-2)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--mono)",
          fontSize: 10,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--accent)",
          marginBottom: compact ? 4 : 6,
        }}
      >
        Data confidence
      </div>
      <p style={{ margin: 0 }}>
        <strong style={{ color: "var(--text-1)", fontWeight: 500 }}>
          Prices are model-estimated, not live broker quotes.
        </strong>{" "}
        Option premiums use Black–Scholes with {volInputLabel(p.volInput)}; underlying
        from {spotSource}
        {calibrated ? ` · calibrated ${calibrated}` : ""}.
      </p>
      {p.dataAgeWarning && (
        <p style={{ margin: "6px 0 0", color: "var(--negative)" }}>{p.dataAgeWarning}</p>
      )}
    </div>
  );
}
