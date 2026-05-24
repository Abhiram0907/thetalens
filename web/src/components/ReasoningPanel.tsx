import { useEffect, useRef } from "react";
import { NODE_COLORS } from "../data/mockData";
import type { ReasoningStep } from "../types";

type ReasoningPanelProps = {
  steps: ReasoningStep[];
  visibleCount: number;
};

export function ReasoningPanel({ steps, visibleCount }: ReasoningPanelProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [visibleCount]);

  return (
    <div
      className="analysis-reasoning"
      style={{
        width: 300,
        flexShrink: 0,
        padding: "28px 20px",
        borderLeft: "1px solid var(--border)",
        overflow: "auto",
        animation: "fadeIn 0.7s var(--ease) 0.2s both",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontFamily: "var(--mono)",
          color: "var(--text-3)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: 20,
        }}
      >
        Agent Reasoning
      </div>

      {steps.slice(0, visibleCount).map((step, i) => (
        <div
          key={`${step.node}-${step.delay}-${i}`}
          style={{
            display: "flex",
            gap: 10,
            marginBottom: 14,
            animation: "slideUp 0.4s var(--ease) both",
          }}
        >
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              marginTop: 6,
              flexShrink: 0,
              background: NODE_COLORS[step.node] ?? "var(--text-3)",
            }}
          />
          <div>
            <div
              style={{
                fontSize: 10,
                fontFamily: "var(--mono)",
                color: NODE_COLORS[step.node] ?? "var(--text-3)",
                letterSpacing: "0.04em",
                marginBottom: 2,
              }}
            >
              {step.node}
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: "var(--text-2)",
                lineHeight: 1.5,
              }}
            >
              {step.message}
            </div>
          </div>
        </div>
      ))}

      {visibleCount < steps.length && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "var(--text-3)",
              animation: "pulse 1.4s ease infinite",
            }}
          />
          <span
            style={{
              fontSize: 11,
              color: "var(--text-3)",
              fontStyle: "italic",
            }}
          >
            thinking…
          </span>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
