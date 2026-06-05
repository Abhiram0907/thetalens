import type { CSSProperties, ReactNode } from "react";
import { ThetaLensLogoButton } from "./ThetaLensLogoButton";

const phaseLabelStyle: CSSProperties = {
  fontSize: 11,
  fontFamily: "var(--mono)",
  color: "var(--text-3)",
};

type AgentPhaseLayoutProps = {
  phaseLabel: string;
  accentColor?: string;
  onReset: () => void;
  children: ReactNode;
};

export function AgentPhaseLayout({
  phaseLabel,
  accentColor,
  onReset,
  children,
}: AgentPhaseLayoutProps) {
  return (
    <div className="agent-phase-wrapper">
      <header className="agent-phase-header">
        <ThetaLensLogoButton accentColor={accentColor} onClick={onReset} />
        <span style={phaseLabelStyle}>{phaseLabel}</span>
      </header>
      <div className="agent-phase-body">{children}</div>
    </div>
  );
}
