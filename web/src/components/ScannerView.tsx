import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  fetchScanner,
  type ScannerStock,
  type SeedContext,
} from "../api/client";

type SortKey = "opportunity" | "correlation" | "ivRank" | "beta";

type ScannerViewProps = {
  seedTicker: string;
  onBuildStrategies: (ticker: string, stock: ScannerStock) => void;
  onBack: () => void;
  accentColor: string;
};

export function ScannerView({
  seedTicker,
  onBuildStrategies,
  onBack,
  accentColor,
}: ScannerViewProps) {
  const [stocks, setStocks] = useState<ScannerStock[]>([]);
  const [seedCtx, setSeedCtx] = useState<SeedContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("opportunity");
  const [hasAnimated, setHasAnimated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    setHasAnimated(false);
    fetchScanner(seedTicker)
      .then((res) => {
        if (!cancelled) {
          setStocks(res.results);
          setSeedCtx(res.seedContext);
          setLoading(false);
          requestAnimationFrame(() => setHasAnimated(true));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Scanner failed");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [seedTicker]);

  const sorted = useMemo(() => {
    const arr = [...stocks];
    switch (sortBy) {
      case "opportunity":
        arr.sort((a, b) => b.opportunityScore - a.opportunityScore);
        break;
      case "correlation":
        arr.sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
        break;
      case "ivRank":
        arr.sort((a, b) => (b.ivRank ?? 0) - (a.ivRank ?? 0));
        break;
      case "beta":
        arr.sort((a, b) => Math.abs(b.beta) - Math.abs(a.beta));
        break;
    }
    return arr;
  }, [stocks, sortBy]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button type="button" onClick={onBack} style={styles.backBtn}>
          &larr; Back
        </button>
        <h2 style={styles.title}>
          Stocks similar to{" "}
          <span style={{ color: accentColor }}>{seedTicker}</span>
        </h2>
        <p style={styles.subtitle}>
          Ranked by opportunity score &middot; IV rank, earnings, correlation,
          and volatility
        </p>
      </div>

      {loading && (
        <>
          <div style={styles.loadingRow}>
            <div
              style={{
                ...styles.pulseCircle,
                background: accentColor,
              }}
            />
            <span style={styles.loadingText}>
              Scanning peers &mdash; enriching with IV rank, earnings,
              sector&hellip;
            </span>
          </div>
          <div style={styles.shimmerSeed} />
          <div style={styles.grid}>
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                style={{
                  ...styles.shimmerCard,
                  animationDelay: `${i * 150}ms`,
                }}
              />
            ))}
          </div>
        </>
      )}

      {error && <div style={styles.errorBox}>{error}</div>}

      {!loading && !error && stocks.length === 0 && (
        <div style={styles.emptyBox}>
          No similar stocks found for {seedTicker}. Try a different ticker.
        </div>
      )}

      {!loading && !error && stocks.length > 0 && (
        <>
          {seedCtx && (
            <SeedCard seed={seedCtx} accentColor={accentColor} />
          )}

          <div style={styles.sortBar}>
            <span style={styles.sortLabel}>Sort by</span>
            {(
              [
                ["opportunity", "Opportunity"],
                ["correlation", "Correlation"],
                ["ivRank", "IV Rank"],
                ["beta", "Beta"],
              ] as [SortKey, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setSortBy(key)}
                style={{
                  ...styles.sortBtn,
                  ...(sortBy === key
                    ? { color: accentColor, borderColor: accentColor }
                    : {}),
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div style={styles.grid}>
            {sorted.map((stock, i) => (
              <StockCard
                key={stock.ticker}
                stock={stock}
                seedIvRank={seedCtx?.ivRank ?? null}
                index={i}
                skipAnimation={hasAnimated}
                accentColor={accentColor}
                onBuild={() => onBuildStrategies(stock.ticker, stock)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Seed context card                                                         */
/* -------------------------------------------------------------------------- */

function SeedCard({
  seed,
  accentColor,
}: {
  seed: SeedContext;
  accentColor: string;
}) {
  const changePos = seed.changePct >= 0;
  return (
    <div
      style={{
        ...styles.seedCard,
        borderColor: accentColor + "55",
      }}
    >
      <div style={styles.seedTop}>
        <div>
          <span style={styles.seedBadge}>SEED</span>
          <span style={styles.seedTicker}>{seed.ticker}</span>
          <span style={styles.seedName}>{seed.name}</span>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={styles.seedPrice}>${seed.price.toFixed(2)}</div>
          <div
            style={{
              ...styles.seedChange,
              color: changePos ? "var(--positive)" : "var(--negative)",
            }}
          >
            {changePos ? "+" : ""}
            {seed.changePct.toFixed(2)}%
          </div>
        </div>
      </div>
      <div style={styles.seedMeta}>
        <span>{seed.sector}</span>
        <span>&middot;</span>
        <span>{seed.marketCapLabel} Cap</span>
      </div>
      <div style={styles.seedStats}>
        <SeedStat label="Beta (SPY)" value={seed.betaSpy.toFixed(2)} />
        <SeedStat
          label="30d RVol"
          value={`${seed.realizedVol30d.toFixed(1)}%`}
        />
        <SeedStat
          label="IV Rank"
          value={seed.ivRank != null ? `${seed.ivRank.toFixed(0)}` : "—"}
        />
      </div>
    </div>
  );
}

function SeedStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.seedStatCell}>
      <div style={styles.seedStatLabel}>{label}</div>
      <div style={styles.seedStatValue}>{value}</div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Stock card                                                                */
/* -------------------------------------------------------------------------- */

function StockCard({
  stock,
  seedIvRank,
  index,
  skipAnimation,
  accentColor,
  onBuild,
}: {
  stock: ScannerStock;
  seedIvRank: number | null;
  index: number;
  skipAnimation: boolean;
  accentColor: string;
  onBuild: () => void;
}) {
  const changePositive = stock.changePct >= 0;
  const ivr = stock.ivRank;
  const ivrColor =
    ivr == null
      ? "var(--text-4)"
      : ivr >= 70
        ? "var(--negative)"
        : ivr >= 30
          ? "var(--text-2)"
          : "var(--positive)";

  const relativeIv =
    ivr != null && seedIvRank != null
      ? ivr < seedIvRank - 15
        ? "Cheaper"
        : ivr > seedIvRank + 15
          ? "Pricier"
          : "Similar"
      : null;

  const relativeColor =
    relativeIv === "Cheaper"
      ? "var(--positive)"
      : relativeIv === "Pricier"
        ? "var(--negative)"
        : "var(--text-4)";

  return (
    <div
      style={{
        ...styles.card,
        ...(skipAnimation
          ? {}
          : { animation: `fadeIn 0.5s var(--ease) ${index * 100}ms both` }),
      }}
    >
      {/* Header row */}
      <div style={styles.cardHeader}>
        <div>
          <div style={styles.ticker}>{stock.ticker}</div>
          <div style={styles.name}>{stock.name}</div>
          <div style={styles.sectorLine}>
            {stock.sector} &middot; {stock.marketCapLabel} Cap
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={styles.price}>${stock.price.toFixed(2)}</div>
          <div
            style={{
              ...styles.change,
              color: changePositive ? "var(--positive)" : "var(--negative)",
            }}
          >
            {changePositive ? "+" : ""}
            {stock.changePct.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Opportunity score bar */}
      <div style={styles.oppRow}>
        <span style={styles.oppLabel}>Opportunity</span>
        <div style={styles.oppBarOuter}>
          <div
            style={{
              ...styles.oppBarInner,
              width: `${stock.opportunityScore}%`,
              background: accentColor,
            }}
          />
        </div>
        <span style={styles.oppValue}>{stock.opportunityScore.toFixed(0)}</span>
      </div>

      {/* Stats grid */}
      <div style={styles.statsGrid}>
        <StatCell label="Beta" value={stock.beta.toFixed(2)} />
        <StatCell
          label="30d RVol"
          value={`${stock.realizedVol30d.toFixed(1)}%`}
        />
        <StatCell
          label="Corr"
          value={stock.correlation.toFixed(2)}
        />
        <StatCell
          label="IV Rank"
          value={ivr != null ? `${ivr.toFixed(0)}` : "—"}
          valueColor={ivrColor}
        />
        <StatCell
          label="IV-RV"
          value={
            stock.ivRvSpread != null
              ? `${stock.ivRvSpread > 0 ? "+" : ""}${stock.ivRvSpread.toFixed(1)}%`
              : "—"
          }
          valueColor={
            stock.ivRvSpread != null && stock.ivRvSpread > 5
              ? "var(--negative)"
              : stock.ivRvSpread != null && stock.ivRvSpread < -5
                ? "var(--positive)"
                : "var(--text-2)"
          }
        />
        <StatCell
          label="vs Seed"
          value={relativeIv ?? "—"}
          valueColor={relativeColor}
        />
      </div>

      {/* Earnings badge */}
      {stock.earningsWithin30d && stock.earningsDate && (
        <div style={styles.earningsBadge}>
          Earnings {stock.earningsDate} &mdash;{" "}
          {Math.ceil(
            (new Date(stock.earningsDate).getTime() - Date.now()) /
              86_400_000,
          )}{" "}
          days
        </div>
      )}

      <button
        type="button"
        onClick={onBuild}
        style={{ ...styles.buildBtn, background: accentColor }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = "0.9";
          e.currentTarget.style.transform = "translateY(-1px)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = "1";
          e.currentTarget.style.transform = "translateY(0)";
        }}
      >
        Build Strategies
      </button>
    </div>
  );
}

function StatCell({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div style={styles.statCell}>
      <div style={styles.statLabel}>{label}</div>
      <div
        style={{
          ...styles.statValue,
          ...(valueColor ? { color: valueColor } : {}),
        }}
      >
        {value}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Styles                                                                    */
/* -------------------------------------------------------------------------- */

const styles: Record<string, CSSProperties> = {
  container: {
    maxWidth: 720,
    margin: "0 auto",
    padding: "32px 24px",
    height: "100%",
    overflowY: "auto",
  },
  header: { marginBottom: 28 },
  backBtn: {
    background: "none",
    border: "none",
    color: "var(--text-3)",
    fontSize: 12,
    fontFamily: "var(--mono)",
    cursor: "pointer",
    padding: "4px 0",
    marginBottom: 16,
    transition: "color 0.2s",
  },
  title: {
    fontFamily: "var(--serif)",
    fontSize: 24,
    fontWeight: 300,
    color: "var(--text-1)",
    margin: 0,
  },
  subtitle: {
    fontFamily: "var(--sans)",
    fontSize: 12,
    color: "var(--text-3)",
    marginTop: 6,
    margin: "6px 0 0",
  },

  /* loading */
  loadingRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 20,
  },
  pulseCircle: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    animation: "pulse 1.2s ease infinite",
  },
  loadingText: {
    fontSize: 12,
    fontFamily: "var(--mono)",
    color: "var(--text-3)",
  },
  shimmerSeed: {
    height: 100,
    borderRadius: 12,
    marginBottom: 16,
    background:
      "linear-gradient(90deg, var(--bg-surface) 0%, var(--bg-elevated) 50%, var(--bg-surface) 100%)",
    backgroundSize: "200% 100%",
    animation: "shimmer 2s ease infinite",
  },

  /* seed card */
  seedCard: {
    background: "var(--bg-surface)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "18px 22px",
    marginBottom: 20,
  },
  seedTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  seedBadge: {
    display: "inline-block",
    fontSize: 9,
    fontFamily: "var(--mono)",
    fontWeight: 700,
    letterSpacing: "0.1em",
    color: "var(--text-4)",
    background: "var(--bg-elevated)",
    borderRadius: 4,
    padding: "2px 6px",
    marginRight: 8,
    verticalAlign: "middle",
  },
  seedTicker: {
    fontFamily: "var(--mono)",
    fontSize: 16,
    fontWeight: 600,
    color: "var(--text-1)",
    letterSpacing: "0.04em",
    verticalAlign: "middle",
  },
  seedName: {
    fontFamily: "var(--sans)",
    fontSize: 12,
    color: "var(--text-3)",
    marginLeft: 8,
    verticalAlign: "middle",
  },
  seedPrice: { fontFamily: "var(--mono)", fontSize: 15, color: "var(--text-1)" },
  seedChange: { fontFamily: "var(--mono)", fontSize: 11, marginTop: 2 },
  seedMeta: {
    fontFamily: "var(--sans)",
    fontSize: 11,
    color: "var(--text-4)",
    marginBottom: 12,
    display: "flex",
    gap: 6,
  },
  seedStats: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: 12,
    borderTop: "1px solid var(--border)",
    paddingTop: 12,
  },
  seedStatCell: { textAlign: "center" as const },
  seedStatLabel: {
    fontFamily: "var(--mono)",
    fontSize: 9,
    color: "var(--text-4)",
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    marginBottom: 3,
  },
  seedStatValue: {
    fontFamily: "var(--mono)",
    fontSize: 14,
    color: "var(--text-2)",
    fontWeight: 500,
  },

  /* sort bar */
  sortBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 16,
  },
  sortLabel: {
    fontFamily: "var(--mono)",
    fontSize: 10,
    color: "var(--text-4)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.06em",
    marginRight: 4,
  },
  sortBtn: {
    background: "none",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: "4px 10px",
    fontSize: 11,
    fontFamily: "var(--mono)",
    color: "var(--text-3)",
    cursor: "pointer",
    transition: "all 0.2s",
  },

  /* grid */
  grid: { display: "flex", flexDirection: "column", gap: 14 },

  /* stock card */
  card: {
    background: "var(--bg-surface)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "18px 20px",
    transition: "border-color 0.3s",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 10,
  },
  ticker: {
    fontFamily: "var(--mono)",
    fontSize: 17,
    fontWeight: 600,
    color: "var(--text-1)",
    letterSpacing: "0.04em",
  },
  name: {
    fontFamily: "var(--sans)",
    fontSize: 12,
    color: "var(--text-3)",
    marginTop: 1,
  },
  sectorLine: {
    fontFamily: "var(--sans)",
    fontSize: 11,
    color: "var(--text-4)",
    marginTop: 3,
  },
  price: { fontFamily: "var(--mono)", fontSize: 15, color: "var(--text-1)" },
  change: { fontFamily: "var(--mono)", fontSize: 11, marginTop: 2 },

  /* opportunity bar */
  oppRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  oppLabel: {
    fontFamily: "var(--mono)",
    fontSize: 9,
    color: "var(--text-4)",
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    flexShrink: 0,
    width: 72,
  },
  oppBarOuter: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    background: "var(--bg-elevated)",
    overflow: "hidden",
  },
  oppBarInner: {
    height: "100%",
    borderRadius: 2,
    transition: "width 0.6s var(--ease)",
  },
  oppValue: {
    fontFamily: "var(--mono)",
    fontSize: 12,
    color: "var(--text-2)",
    fontWeight: 600,
    width: 28,
    textAlign: "right" as const,
  },

  /* stats grid */
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: 10,
    padding: "12px 0",
    borderTop: "1px solid var(--border)",
    borderBottom: "1px solid var(--border)",
    marginBottom: 12,
  },
  statCell: { textAlign: "center" as const },
  statLabel: {
    fontFamily: "var(--mono)",
    fontSize: 9,
    color: "var(--text-4)",
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    marginBottom: 3,
  },
  statValue: {
    fontFamily: "var(--mono)",
    fontSize: 13,
    color: "var(--text-2)",
    fontWeight: 500,
  },

  /* earnings badge */
  earningsBadge: {
    fontFamily: "var(--mono)",
    fontSize: 11,
    color: "var(--text-3)",
    background: "rgba(212, 137, 107, 0.12)",
    border: "1px solid rgba(212, 137, 107, 0.25)",
    borderRadius: 6,
    padding: "5px 10px",
    marginBottom: 12,
    textAlign: "center" as const,
  },

  /* build btn */
  buildBtn: {
    width: "100%",
    padding: "10px 0",
    fontSize: 13,
    fontFamily: "var(--sans)",
    fontWeight: 500,
    color: "#080808",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    letterSpacing: "0.04em",
    transition: "all 0.2s",
  },

  /* shimmer */
  shimmerCard: {
    height: 240,
    borderRadius: 12,
    background:
      "linear-gradient(90deg, var(--bg-surface) 0%, var(--bg-elevated) 50%, var(--bg-surface) 100%)",
    backgroundSize: "200% 100%",
    animation: "shimmer 2s ease infinite",
  },
  errorBox: {
    padding: "16px 18px",
    borderRadius: 10,
    background: "rgba(212, 137, 107, 0.12)",
    border: "1px solid rgba(212, 137, 107, 0.35)",
    fontSize: 13,
    color: "var(--text-2)",
    lineHeight: 1.5,
  },
  emptyBox: {
    padding: "32px 18px",
    textAlign: "center" as const,
    fontSize: 13,
    color: "var(--text-3)",
    fontFamily: "var(--sans)",
  },
};
