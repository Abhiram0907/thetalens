import type { CSSProperties } from "react";

const logoButtonStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  background: "none",
  border: "none",
  cursor: "pointer",
  padding: 0,
};

const thetaStyle = (accentColor: string): CSSProperties => ({
  fontFamily: "var(--serif)",
  fontSize: 24,
  fontWeight: 300,
  color: accentColor,
});

const wordmarkStyle: CSSProperties = {
  fontFamily: "var(--serif)",
  fontSize: 16,
  fontWeight: 400,
  color: "var(--text-1)",
  letterSpacing: "0.08em",
};

type ThetaLensLogoButtonProps = {
  accentColor?: string;
  onClick: () => void;
};

export function ThetaLensLogoButton({
  accentColor = "var(--accent)",
  onClick,
}: ThetaLensLogoButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={logoButtonStyle}
      aria-label="New view"
    >
      <span style={thetaStyle(accentColor)}>θ</span>
      <span style={wordmarkStyle}>thetalens</span>
    </button>
  );
}
