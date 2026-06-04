from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.llm.prompts import INTENT_PROMPT
from app.llm_config import get_llm_config
from app.schemas.intent import IntentSlots


@lru_cache
def _chat_model() -> BaseChatModel:
    return get_llm_config().create_model()


def _intent_chain():
    return INTENT_PROMPT | _chat_model().with_structured_output(IntentSlots)


async def parse_intent_slots(query: str) -> IntentSlots:
    """LangChain structured intent extraction (Gemini or Ollama per llm.yaml)."""
    return await _intent_chain().ainvoke({"query": query})
