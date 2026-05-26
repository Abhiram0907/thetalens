import { useCallback, useRef, useState } from "react";
import { API_BASE } from "../lib/apiBase";
import {
  userFacingAgentMessage,
  userFacingNetworkError,
  userFacingStreamError,
} from "../lib/safeErrors";
import type {
  AgentEvent,
  ContextData,
  ThesisRequest,
  TypedAgentEvent,
} from "../types/agent";

export type AgentBuildPayload = {
  strategies: unknown[];
  parsed_view?: {
    direction: string;
    direction_icon: string;
    magnitude: string;
    horizon: string;
    horizon_label: string;
    volatility_view: string;
    risk_budget: string;
    underlying: string;
    underlying_price: number;
    iv_rank: number;
    iv_label: string;
  };
  reasoning_steps?: Array<{ node: string; message: string; delay: number }>;
  underlying_price?: number;
};

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface AgentStreamState {
  events: TypedAgentEvent[];
  isStreaming: boolean;
  context: ContextData | null;
  strategies: unknown[] | null;
  buildPayload: AgentBuildPayload | null;
  error: string | null;
  currentStep: number;
}

const INITIAL_STATE: AgentStreamState = {
  events: [],
  isStreaming: false,
  context: null,
  strategies: null,
  buildPayload: null,
  error: null,
  currentStep: 0,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAgentStream(apiBase = API_BASE) {
  const [state, setState] = useState<AgentStreamState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(
    async (request: ThesisRequest) => {
      // Reset state
      setState({ ...INITIAL_STATE, isStreaming: true });

      // Abort any previous stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const resp = await fetch(`${apiBase}/api/agent/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
          signal: controller.signal,
        });

        if (!resp.ok) {
          setState((s) => ({
            ...s,
            isStreaming: false,
            error: userFacingStreamError(resp.status),
          }));
          return;
        }

        const reader = resp.body?.getReader();
        if (!reader) {
          setState((s) => ({ ...s, isStreaming: false, error: "No response body" }));
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            try {
              const event = JSON.parse(jsonStr) as AgentEvent;
              const typed = event as unknown as TypedAgentEvent;

              setState((prev) => {
                const next = { ...prev, events: [...prev.events, typed] };

                switch (typed.type) {
                  case "thinking":
                  case "tool_call":
                  case "tool_result":
                    next.currentStep = (typed.data as { step?: number }).step ?? prev.currentStep;
                    break;
                  case "reasoning":
                    next.currentStep = (typed.data as { step?: number }).step ?? prev.currentStep;
                    break;
                  case "context":
                    next.context = typed.data as unknown as ContextData;
                    break;
                  case "strategies": {
                    const payload = typed.data as AgentBuildPayload;
                    next.strategies = payload.strategies;
                    next.buildPayload = payload;
                    break;
                  }
                  case "error":
                    next.error = userFacingAgentMessage(
                      (typed.data as { message: string }).message,
                    );
                    break;
                  case "done":
                    next.isStreaming = false;
                    break;
                }

                return next;
              });
            } catch {
              // Skip malformed lines
            }
          }
        }

        // Stream ended
        setState((s) => ({ ...s, isStreaming: s.isStreaming ? false : s.isStreaming }));
      } catch (err: unknown) {
        if ((err as Error)?.name === "AbortError") return;
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: userFacingNetworkError(),
        }));
      }
    },
    [apiBase],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({ ...s, isStreaming: false }));
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, start, stop, reset };
}
