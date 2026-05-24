interface IVRankBadgeProps {
  rank: number;       // 0-100
  regime: "Low" | "Mid" | "High";
  rv?: number;        // current 30d realized vol
  compact?: boolean;
}

export function IVRankBadge({ rank, regime, rv, compact = false }: IVRankBadgeProps) {
  const cls = `iv-rank-badge iv-rank-badge--${regime.toLowerCase()}`;

  if (compact) {
    return (
      <span className={cls}>
        IV {rank}
      </span>
    );
  }

  return (
    <span className={cls}>
      <span>IV Rank {rank}</span>
      <span className="iv-rank-badge__bar">
        <span
          className="iv-rank-badge__fill"
          style={{ width: `${Math.min(100, Math.max(0, rank))}%` }}
        />
      </span>
      {rv != null && <span>{rv.toFixed(1)}%</span>}
    </span>
  );
}
