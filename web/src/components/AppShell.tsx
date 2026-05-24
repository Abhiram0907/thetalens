import type { ReactNode } from "react";
import { FinancialDisclaimer } from "./FinancialDisclaimer";

type AppShellProps = {
  children: ReactNode;
  showFooter?: boolean;
};

export function AppShell({ children, showFooter = true }: AppShellProps) {
  return (
    <>
      {children}
      {showFooter && <FinancialDisclaimer variant="footer" />}
    </>
  );
}
