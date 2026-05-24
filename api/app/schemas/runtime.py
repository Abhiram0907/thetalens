from pydantic import BaseModel


class ProviderSnapshot(BaseModel):
    model: str
    resolved: str
    temperature: float
    base_url: str | None = None


class RuntimeResponse(BaseModel):
    active: str
    alias: str
    model: str
    temperature: float
    api_key_configured: bool | None = None
    providers: dict[str, ProviderSnapshot]
    aliases: dict[str, dict[str, str]]
    config_file: str
    reload_hint: str
