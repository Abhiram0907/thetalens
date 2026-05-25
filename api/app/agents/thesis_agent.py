"""
Trade Thesis Agent — ReAct loop with streaming reasoning.

Takes a parsed user intent, runs a multi-step tool-calling loop via Gemma/Gemini,
and yields SSE events for each thought/tool-call/result. When the LLM emits a
final answer (no more tool calls), it returns an enriched context dict that feeds
into the existing strategy_builder.

Works with Google GenAI (Gemma / Gemini) function calling. Falls back to a
structured-prompt approach if function calling is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

from pydantic import BaseModel

from app.tools.registry import (
    PolygonClient,
    derive_magnitude,
    get_all_tools,
    get_tool,
    tools_as_openai_schema,
)
from app.services.strategy_builder import parse_horizon_days


# ---------------------------------------------------------------------------
# SSE event types
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING = "reasoning"
    CONTEXT = "context"          # enriched context for strategy builder
    STRATEGIES = "strategies"    # final ranked strategies
    ERROR = "error"
    DONE = "done"


@dataclass
class AgentEvent:
    type: EventType
    data: dict[str, Any]
    ts: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = json.dumps({"type": self.type.value, "data": self.data, "ts": self.ts})
        return f"data: {payload}\n\n"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are ThetaLens, an expert options strategist agent. The user provides ONLY:
underlying, horizon, risk budget, and sometimes direction. They do NOT specify magnitude.

Your job is to RESEARCH the market, infer direction when the user is unsure, and
CALCULATE magnitude before recommending structures.

## Your process
1. ALWAYS call get_iv_rank first — you need the vol regime before anything else.
2. Call get_upcoming_earnings to check for catalysts in the trade window.
3. Call get_news_sentiment to cross-check the user's directional thesis or infer one.
4. Call get_historical_post_earnings_move if earnings fall in the window.
5. Call get_expected_move to learn the market's implied move over the horizon.
6. Call calculate_magnitude to derive the expected move magnitude from market data.
7. Call assess_structure_fit with your findings (include the calculated magnitude).
8. ONLY THEN write your final analysis.

## Rules
- Call tools ONE AT A TIME. Wait for results before deciding next step.
- Think out loud before each tool call: explain WHY you're calling it.
- NEVER ask the user for magnitude — calculate it from get_expected_move and history.
- NEVER ask the user for direction. If the direction is missing, uncertain, or marked
  "infer", infer it from sentiment, IV regime, earnings/catalyst risk, and expected move.
  If evidence is mixed or mainly volatility/catalyst driven, use Neutral.
- After all tools, write a FINAL ANALYSIS that includes:
  a) Vol regime assessment
  b) Calculated magnitude and how you derived it
  c) Catalyst risk
  d) News alignment with thesis
  e) Recommended structures with reasoning
  f) Structures to AVOID and why
  g) Any warnings or caveats
- Be specific with numbers. Quote the IV rank, expected move, earnings dates.
- If the user's direction contradicts market data (e.g., bullish thesis but all
  recent news is bearish), flag it diplomatically.
- NEVER hallucinate data. Only cite numbers from tool results.
- This is educational research tooling only. Do NOT present output as financial,
  investment, or trading advice. Frame recommendations as hypothetical structures
  for analysis, not instructions to trade.
"""

INFER_DIRECTION_MARKERS = {
    "",
    "infer",
    "inferred",
    "unknown",
    "unsure",
    "uncertain",
    "not sure",
    "agentic",
    "auto",
}

DIRECTION_ALIASES = {
    "bull": "bullish",
    "bullish": "bullish",
    "up": "bullish",
    "bear": "bearish",
    "bearish": "bearish",
    "down": "bearish",
    "neutral": "neutral",
    "range": "neutral",
    "sideways": "neutral",
}


def _normal_direction(value: Any) -> str:
    return str(value or "").strip().lower()


def _needs_direction_inference(value: Any) -> bool:
    direction = _normal_direction(value)
    return direction in INFER_DIRECTION_MARKERS or direction not in DIRECTION_ALIASES


def _infer_direction_from_context(enriched_context: dict[str, Any]) -> tuple[str, str]:
    """Infer a trade direction from researched signals when the user did not give one."""
    news = enriched_context.get("get_news_sentiment") or {}
    sentiment = _normal_direction(news.get("overall_sentiment"))
    score = news.get("sentiment_score")
    if isinstance(score, (int, float)):
        if score >= 0.25:
            return "bullish", f"recent news sentiment is bullish with score {score}"
        if score <= -0.25:
            return "bearish", f"recent news sentiment is bearish with score {score}"

    if sentiment in ("bullish", "bearish"):
        return sentiment, f"recent news sentiment is {sentiment}"

    earnings = enriched_context.get("get_upcoming_earnings") or {}
    iv = enriched_context.get("get_iv_rank") or {}
    expected = enriched_context.get("get_expected_move") or {}
    earnings_in_window = bool(earnings.get("earnings_in_trade_window"))
    iv_regime = _normal_direction(iv.get("regime"))
    expected_move = expected.get("expected_move_pct")

    if earnings_in_window:
        if iv_regime == "high":
            return "neutral", "earnings are inside the trade window and IV is elevated"
        if isinstance(expected_move, (int, float)) and expected_move >= 4:
            return "neutral", f"earnings are inside the trade window with a {expected_move}% expected move"
        return "neutral", "earnings are inside the trade window without a clear directional sentiment edge"

    if iv_regime == "high":
        return "neutral", "IV is elevated and directional evidence is mixed"

    return "neutral", "directional evidence is mixed, so the agent is using a neutral/volatility view"


def _format_llm_error_internal(exc: Exception) -> str:
    """Detailed error for server logs only."""
    import httpx

    from app.core.security import redact_secrets

    if isinstance(exc, httpx.HTTPStatusError):
        detail = exc.response.text[:500] if exc.response is not None else ""
        msg = f"HTTP {exc.response.status_code}: {detail or exc.response.reason_phrase}"
        return redact_secrets(msg)
    if isinstance(exc, httpx.TimeoutException):
        return "Request timed out"
    msg = str(exc).strip()
    if msg:
        return redact_secrets(msg)
    return f"{type(exc).__name__} (no details)"


def _format_llm_error_client(exc: Exception) -> str:
    """Generic message for SSE clients."""
    from app.core.security import LLM_UNAVAILABLE

    import httpx

    if isinstance(exc, (httpx.HTTPError, RuntimeError)):
        return LLM_UNAVAILABLE
    return LLM_UNAVAILABLE


def _coerce_tool_arguments(name: str, arguments: dict) -> dict:
    """Coerce string-typed numeric args from the LLM into proper Python types."""
    tool_spec = get_tool(name)
    if not tool_spec:
        return arguments

    props = tool_spec.parameters.get("properties", {})
    coerced = dict(arguments)
    for key, schema in props.items():
        if key not in coerced:
            continue
        val = coerced[key]
        typ = schema.get("type")
        try:
            if typ == "number" and isinstance(val, str):
                coerced[key] = float(val) if "." in val else int(val)
            elif typ == "boolean" and isinstance(val, str):
                coerced[key] = val.lower() in ("true", "yes", "1")
        except (ValueError, TypeError):
            continue
    return coerced


class ThesisAgent:
    """
    Runs a ReAct loop for a user's trade thesis.

    Usage:
        agent = ThesisAgent(polygon_client, llm_client)
        async for event in agent.run(parsed_intent):
            yield event.to_sse()
    """

    MAX_STEPS = 10

    def __init__(
        self,
        polygon_client: PolygonClient,
        llm_provider: str = "google",
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.3,
    ):
        self.polygon = polygon_client
        self.llm_provider = llm_provider
        self.model = model or "gemma-4-26b-a4b-it"
        self.api_key = api_key
        self.temperature = temperature

    # ------------------------------------------------------------------
    # LLM call (supports Google GenAI function calling)
    # ------------------------------------------------------------------

    async def _call_llm(self, messages: list[dict], tools: list[dict]) -> dict:
        """
        Call the LLM with function-calling support.
        Returns the raw response dict with 'content' and optional 'tool_calls'.
        """
        if self.llm_provider == "google":
            return await self._call_google(messages, tools)
        else:
            return await self._call_fallback(messages)

    async def _call_google(self, messages: list[dict], tools: list[dict]) -> dict:
        """Google GenAI via REST (works with Gemma and Gemini models)."""
        import httpx

        # Convert OpenAI-style messages to Google format
        google_contents = []
        for msg in messages:
            if msg["role"] == "system":
                continue  # handled separately
            role = "model" if msg["role"] == "assistant" else "user"

            # Handle tool results
            if msg["role"] == "tool":
                google_contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("name", "unknown"),
                            "response": {"result": msg["content"]},
                        }
                    }],
                })
                continue

            parts = []
            if isinstance(msg.get("content"), str) and msg["content"]:
                parts.append({"text": msg["content"]})

            # Handle assistant tool calls
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    part: dict[str, Any] = {
                        "functionCall": {
                            "name": tc["function"]["name"],
                            "args": json.loads(tc["function"]["arguments"]),
                        }
                    }
                    if tc.get("thought_signature"):
                        part["thoughtSignature"] = tc["thought_signature"]
                    parts.append(part)

            if parts:
                google_contents.append({"role": role, "parts": parts})

        # Build Google function declarations
        google_tools = []
        if tools:
            declarations = []
            for t in tools:
                fn = t["function"]
                params = dict(fn.get("parameters", {}))
                # Google API doesn't accept empty required arrays well
                if "required" in params and not params["required"]:
                    del params["required"]
                declarations.append({
                    "name": fn["name"],
                    "description": fn["description"],
                    "parameters": params,
                })
            google_tools = [{"functionDeclarations": declarations}]

        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        system_instruction = {"parts": [{"text": "\n\n".join(system_msgs)}]} if system_msgs else None

        body: dict[str, Any] = {
            "contents": google_contents,
            "generationConfig": {"temperature": self.temperature},
        }
        if google_tools:
            body["tools"] = google_tools
        if system_instruction:
            body["systemInstruction"] = system_instruction

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        headers = {"x-goog-api-key": self.api_key or ""}

        async with httpx.AsyncClient(timeout=90) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(_format_llm_error_internal(exc)) from exc
            except httpx.TimeoutException as exc:
                raise RuntimeError(_format_llm_error_internal(exc)) from exc
            data = resp.json()

        # Surface API-level errors (e.g. blocked, quota)
        if "error" in data:
            err = data["error"]
            msg = err.get("message") or err.get("status") or json.dumps(err)
            raise RuntimeError(f"Google API error: {msg}")

        # Parse response
        candidates = data.get("candidates", [])
        if not candidates:
            return {"content": "No response from model.", "tool_calls": []}

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = []
        tool_calls = []

        for part in parts:
            if "text" in part:
                text = part["text"]
                if part.get("thought") and not text.strip():
                    continue
                text_parts.append(text)
            elif "functionCall" in part:
                fc = part["functionCall"]
                tc: dict[str, Any] = {
                    "id": f"call_{fc['name']}_{int(time.time())}",
                    "function": {
                        "name": fc["name"],
                        "arguments": json.dumps(fc.get("args", {})),
                    },
                }
                if part.get("thoughtSignature"):
                    tc["thought_signature"] = part["thoughtSignature"]
                tool_calls.append(tc)

        return {
            "content": "\n".join(text_parts),
            "tool_calls": tool_calls,
        }

    async def _call_fallback(self, messages: list[dict]) -> dict:
        """
        Fallback: prompt-based tool calling for models without function-calling.
        Parses JSON tool calls from the model's text output.
        """
        # Append tool instruction to the last user message
        tool_specs = tools_as_openai_schema()
        tool_instruction = (
            "\n\nAvailable tools:\n"
            + json.dumps(tool_specs, indent=2)
            + '\n\nTo call a tool, output EXACTLY: {"tool_call": {"name": "...", "arguments": {...}}}'
            + "\nTo give your final answer, just write text without a tool_call JSON block."
        )

        modified = list(messages)
        for i in range(len(modified) - 1, -1, -1):
            if modified[i]["role"] == "user":
                modified[i] = dict(modified[i])
                modified[i]["content"] = (modified[i].get("content") or "") + tool_instruction
                break

        # Use langchain or direct API call — simplified here
        # In production, call your existing intent_chain LLM
        return {"content": "Fallback mode — tools unavailable.", "tool_calls": []}

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, arguments: dict) -> dict:
        import logging

        from app.core.security import sanitize_tool_result

        logger = logging.getLogger("thetalens.agent")
        tool_spec = get_tool(name)
        if not tool_spec:
            return {"error": "Unknown tool"}

        try:
            coerced = _coerce_tool_arguments(name, arguments)
            result = await tool_spec.fn(**coerced, polygon_client=self.polygon)
            return sanitize_tool_result(result)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return sanitize_tool_result({"error": "Tool execution failed"})

    # ------------------------------------------------------------------
    # Main agent loop
    # ------------------------------------------------------------------

    async def run(self, parsed_intent: dict) -> AsyncIterator[AgentEvent]:
        """
        Run the agent loop. Yields AgentEvent objects for SSE streaming.

        parsed_intent should include:
            underlying, direction, magnitude, horizon, risk_budget, summary
        """
        ticker = parsed_intent.get("underlying", "SPY")
        direction = parsed_intent.get("direction") or "infer"
        horizon = parsed_intent.get("horizon", "30 days")
        risk_budget = parsed_intent.get("risk_budget", "not specified")
        summary = parsed_intent.get("summary", parsed_intent.get("query", ""))

        direction_line = (
            "Infer from market data"
            if _needs_direction_inference(direction)
            else str(direction)
        )
        user_prompt = (
            f"The user's trade thesis (magnitude NOT provided — you must calculate it):\n"
            f"  Underlying: {ticker}\n"
            f"  Direction: {direction_line}\n"
            f"  Horizon: {horizon}\n"
            f"  Risk budget: {risk_budget}\n"
            f"  Original query: {summary}\n\n"
            f"Research this thesis using the available tools. Calculate magnitude from "
            f"market data, then provide your final analysis with structure recommendations."
        )

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        tools = tools_as_openai_schema()
        enriched_context: dict[str, Any] = {
            "ticker": ticker,
            "direction": direction,
            "horizon": horizon,
            "risk_budget": risk_budget,
        }

        yield AgentEvent(
            type=EventType.THINKING,
            data={"message": f"Analyzing thesis for {ticker}… starting research loop."},
        )

        for step in range(self.MAX_STEPS):
            try:
                response = await self._call_llm(messages, tools)
            except Exception as e:
                yield AgentEvent(
                    type=EventType.ERROR,
                    data={"message": _format_llm_error_client(e), "step": step},
                )
                break

            text = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            # Emit any thinking/reasoning text
            if text.strip():
                yield AgentEvent(
                    type=EventType.THINKING if tool_calls else EventType.REASONING,
                    data={"message": text.strip(), "step": step},
                )

            # No more tool calls → final answer
            if not tool_calls:
                await self._ensure_magnitude(enriched_context)
                enriched_context["agent_analysis"] = text.strip()
                yield AgentEvent(
                    type=EventType.CONTEXT,
                    data=enriched_context,
                )
                break

            # Execute tool calls
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": text}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                if fn_name in {"calculate_magnitude", "assess_structure_fit"}:
                    arg_direction = fn_args.get("direction", enriched_context.get("direction"))
                    if _needs_direction_inference(arg_direction) or enriched_context.get("direction_inference"):
                        inferred, reason = _infer_direction_from_context(enriched_context)
                        enriched_context["direction"] = inferred
                        enriched_context["direction_inference"] = {
                            "inferred": True,
                            "direction": inferred,
                            "reason": reason,
                        }
                        fn_args["direction"] = inferred

                yield AgentEvent(
                    type=EventType.TOOL_CALL,
                    data={"tool": fn_name, "arguments": fn_args, "step": step},
                )

                result = await self._execute_tool(fn_name, fn_args)

                yield AgentEvent(
                    type=EventType.TOOL_RESULT,
                    data={"tool": fn_name, "result": result, "step": step},
                )

                # Store in enriched context
                enriched_context[fn_name] = result
                should_refresh_direction = (
                    _needs_direction_inference(enriched_context.get("direction"))
                    or bool(enriched_context.get("direction_inference"))
                )
                if should_refresh_direction and fn_name in {
                    "get_news_sentiment",
                    "get_upcoming_earnings",
                    "get_iv_rank",
                    "get_expected_move",
                }:
                    inferred, reason = _infer_direction_from_context(enriched_context)
                    enriched_context["direction"] = inferred
                    enriched_context["direction_inference"] = {
                        "inferred": True,
                        "direction": inferred,
                        "reason": reason,
                    }
                if fn_name == "calculate_magnitude" and result.get("magnitude"):
                    enriched_context["magnitude"] = result["magnitude"]

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "content": json.dumps(result),
                })

                # Small delay so frontend can render
                await asyncio.sleep(0.1)

        yield AgentEvent(type=EventType.DONE, data={"steps": step + 1})

    async def _ensure_magnitude(self, enriched_context: dict[str, Any]) -> None:
        """Guarantee magnitude is set from calculate_magnitude tool or market data."""
        if _needs_direction_inference(enriched_context.get("direction")) or enriched_context.get("direction_inference"):
            inferred, reason = _infer_direction_from_context(enriched_context)
            enriched_context["direction"] = inferred
            enriched_context["direction_inference"] = {
                "inferred": True,
                "direction": inferred,
                "reason": reason,
            }

        mag = enriched_context.get("calculate_magnitude") or {}
        direction = enriched_context.get("direction", "neutral")
        mag_direction = _normal_direction(mag.get("direction"))
        magnitude_matches_direction = (
            not mag_direction
            or DIRECTION_ALIASES.get(mag_direction, mag_direction) == _normal_direction(direction)
        )
        if enriched_context.get("magnitude"):
            if magnitude_matches_direction:
                return

        if mag.get("magnitude") and magnitude_matches_direction:
            enriched_context["magnitude"] = mag["magnitude"]
            return

        ticker = enriched_context.get("ticker", "SPY")
        horizon = enriched_context.get("horizon", "30 days")
        try:
            result = await derive_magnitude(
                ticker,
                direction,
                parse_horizon_days(horizon),
                polygon_client=self.polygon,
            )
            enriched_context["calculate_magnitude"] = result
            enriched_context["magnitude"] = result["magnitude"]
        except Exception:
            enriched_context["magnitude"] = "±5% range"


# ---------------------------------------------------------------------------
# Convenience runner for non-streaming contexts
# ---------------------------------------------------------------------------

async def run_thesis_agent(
    parsed_intent: dict,
    polygon_api_key: str,
    llm_api_key: str | None = None,
    model: str = "gemma-4-26b-a4b-it",
) -> dict:
    """
    Non-streaming convenience wrapper. Returns the full enriched context.
    Use for testing or when SSE is not needed.
    """
    client = PolygonClient(api_key=polygon_api_key)
    agent = ThesisAgent(
        polygon_client=client,
        api_key=llm_api_key,
        model=model,
    )

    events: list[dict] = []
    enriched = {}
    async for event in agent.run(parsed_intent):
        events.append({"type": event.type.value, "data": event.data})
        if event.type == EventType.CONTEXT:
            enriched = event.data

    enriched["_events"] = events
    return enriched
