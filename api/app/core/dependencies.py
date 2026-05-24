from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.chains.intent_chain import create_intent_chain
from app.chains.trade_chain import create_trade_chain
from app.config import Settings, get_settings
from app.llm_config import get_llm_config


@lru_cache
def get_llm() -> BaseChatModel:
    return get_llm_config().create_model()


def get_trade_chain():
    return create_trade_chain(get_llm())


def get_intent_chain():
    return create_intent_chain(get_llm())


def get_settings_dep() -> Settings:
    return get_settings()
