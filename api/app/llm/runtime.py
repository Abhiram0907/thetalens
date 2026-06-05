import re
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.llm.prompts import BOTTOM_LINE_PROMPT, INTENT_PROMPT, TICKER_PROMPT
from app.llm_config import get_llm_config
from app.schemas.intent import IntentSlots
from app.schemas.research_brief import BottomLineResult
from app.schemas.research_facts import ResearchFacts
from app.schemas.ticker import TickerResolution

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


@lru_cache
def _chat_model() -> BaseChatModel:
    return get_llm_config().create_model()


def _intent_chain():
    return INTENT_PROMPT | _chat_model().with_structured_output(IntentSlots)


def _ticker_chain():
    return TICKER_PROMPT | _chat_model().with_structured_output(TickerResolution)


def _bottom_line_chain():
    return BOTTOM_LINE_PROMPT | _chat_model().with_structured_output(BottomLineResult)


async def parse_intent_slots(query: str) -> IntentSlots:
    """LangChain structured intent extraction (Gemini or Ollama per llm.yaml)."""
    return await _intent_chain().ainvoke({"query": query})


async def resolve_ticker_llm(query: str) -> str | None:
    """Focused LLM call to map company names / ambiguous references to a US ticker."""
    result: TickerResolution = await _ticker_chain().ainvoke({"query": query})
    sym = (result.underlying or "").strip().upper()
    if _TICKER_RE.fullmatch(sym):
        return sym
    return None


async def synthesize_bottom_line_llm(facts: ResearchFacts) -> str | None:
    """Focused LLM call: 2-sentence bottom line from structured facts."""
    result: BottomLineResult = await _bottom_line_chain().ainvoke(
        {"facts_json": facts.model_dump_json(exclude_none=True)}
    )
    line = (result.bottom_line or "").strip()
    return line or None
