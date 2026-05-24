type MetricCellProps = {
  label: string;
  value: string;
  color?: string;
};

export function MetricCell({ label, value, color }: MetricCellProps) {
  return (
    <div>
      <div
        style={{
          fontSize: 9.5,
          fontFamily: "var(--mono)",
          color: "var(--text-3)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          marginBottom: 3,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 14,
          fontFamily: "var(--mono)",
          fontWeight: 500,
          color: color ?? "var(--text-1)",
        }}
      >
        {value}
      </div>
    </div>
  );
}
