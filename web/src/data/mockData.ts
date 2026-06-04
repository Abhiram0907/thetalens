/** Demo query strings and reasoning node colors for the UI. */

export const DEMO_QUERY =
  "NVDA bearish over the next 3 weeks — max risk $500";

export const VAGUE_DEMO_QUERY = "NVDA might move soon, not sure which way";

export const SCANNER_DEMO_QUERY = "Stocks that move like NBIS";

export const NODE_COLORS: Record<string, string> = {
  "View Parser": "#6b9fd4",
  "Strategy Planner": "#c9a655",
  Pricer: "#5a9e78",
  Critic: "#d4896b",
  Synthesizer: "#dbb963",
};
