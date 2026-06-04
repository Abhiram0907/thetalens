from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

LlmProvider = Literal["gemini", "ollama"]
LLM_YAML_PATH = Path(__file__).resolve().parent.parent / "llm.yaml"
RELOAD_HINT = "Restart the API after changing api/llm.yaml or LLM_ACTIVE in api/.env."


class ProviderConfig(BaseModel):
    model: str
    temperature: float = 0.3
    base_url: str | None = None


class LlmConfigFile(BaseModel):
    active: LlmProvider = "gemini"
    providers: dict[LlmProvider, ProviderConfig]
    aliases: dict[LlmProvider, dict[str, str]] = Field(default_factory=dict)


class LlmConfig(BaseModel):
    """Runtime LLM config: llm.yaml + .env overrides."""

    active: LlmProvider
    providers: dict[LlmProvider, ProviderConfig]
    aliases: dict[LlmProvider, dict[str, str]]
    google_api_key: str = ""

    @property
    def provider(self) -> ProviderConfig:
        return self.providers[self.active]

    @property
    def model_alias(self) -> str:
        return self.provider.model

    def resolve_model(self, provider: LlmProvider | None = None, alias: str | None = None) -> str:
        p = provider or self.active
        name = (alias or self.providers[p].model).strip()
        key = name.lower()
        return self.aliases.get(p, {}).get(key, name)

    def resolve_google_model(self, settings: Settings | None = None) -> str:
        """Resolved Gemini/Gemma model id for agent (REST) and intent (LangChain)."""
        settings = settings or get_settings()
        override = (
            (settings.google_model or "").strip()
            or os.environ.get("GOOGLE_MODEL", "").strip()
            or os.environ.get("AGENT_MODEL", "").strip()
        )
        if override:
            return self.resolve_model(provider="gemini", alias=override)
        return self.resolve_model(provider="gemini")

    def gemini_api_key_configured(self) -> bool:
        return bool(
            self.google_api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )

    def create_model(self) -> BaseChatModel:
        cfg = self.provider
        if self.active == "gemini":
            kwargs: dict = {
                "model": self.resolve_google_model(),
                "temperature": cfg.temperature,
            }
            if self.google_api_key:
                kwargs["api_key"] = self.google_api_key
            return ChatGoogleGenerativeAI(**kwargs)
        return ChatOllama(
            base_url=cfg.base_url or "http://127.0.0.1:11434",
            model=self.resolve_model(),
            temperature=cfg.temperature,
        )

    def unavailable_detail(self) -> str:
        if self.active == "gemini":
            return (
                "Gemini is unavailable. Set GOOGLE_API_KEY in api/.env "
                f"(model: {self.model_alias})."
            )
        alias = self.model_alias
        resolved = self.resolve_model()
        return (
            "Ollama is unavailable. Install Ollama, run `ollama serve`, "
            f"and pull the model: ollama pull {resolved}"
            + (f" (alias: {alias})" if alias != resolved else "")
        )


def _load_yaml(path: Path) -> LlmConfigFile:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return LlmConfigFile.model_validate(raw)


def load_llm_config(settings: Settings | None = None) -> LlmConfig:
    settings = settings or get_settings()
    file_cfg = _load_yaml(LLM_YAML_PATH)
    active: LlmProvider = settings.llm_active or file_cfg.active
    if active not in file_cfg.providers:
        raise ValueError(f"Unknown LLM_ACTIVE={active!r}; providers: {list(file_cfg.providers)}")
    return LlmConfig(
        active=active,
        providers=file_cfg.providers,
        aliases=file_cfg.aliases,
        google_api_key=settings.google_api_key,
    )


@lru_cache
def get_llm_config() -> LlmConfig:
    return load_llm_config()
