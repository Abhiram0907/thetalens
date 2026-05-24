import { DISCLAIMER_FULL, DISCLAIMER_SHORT, DISCLAIMER_STANDARD } from "../lib/disclaimer";

type FinancialDisclaimerProps = {
  variant?: "footer" | "inline" | "banner";
  className?: string;
};

const COPY = {
  footer: DISCLAIMER_STANDARD,
  inline: DISCLAIMER_SHORT,
  banner: DISCLAIMER_FULL,
} as const;

export function FinancialDisclaimer({
  variant = "inline",
  className,
}: FinancialDisclaimerProps) {
  const text = COPY[variant];

  return (
    <p
      className={className ?? `financial-disclaimer financial-disclaimer--${variant}`}
      role="note"
      aria-label="Legal disclaimer"
    >
      {text}
    </p>
  );
}
