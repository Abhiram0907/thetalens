from app.llm_config import LLM_YAML_PATH, RELOAD_HINT, get_llm_config
from app.schemas.runtime import ProviderSnapshot, RuntimeResponse


def build_runtime_response() -> RuntimeResponse:
    cfg = get_llm_config()
    return RuntimeResponse(
        active=cfg.active,
        alias=cfg.model_alias,
        model=cfg.resolve_model(),
        temperature=cfg.provider.temperature,
        api_key_configured=cfg.gemini_api_key_configured() if cfg.active == "gemini" else None,
        providers={
            name: ProviderSnapshot(
                model=p.model,
                resolved=cfg.resolve_model(name, p.model),
                temperature=p.temperature,
                base_url=p.base_url,
            )
            for name, p in cfg.providers.items()
        },
        aliases=cfg.aliases,
        config_file=str(LLM_YAML_PATH),
        reload_hint=RELOAD_HINT,
    )
