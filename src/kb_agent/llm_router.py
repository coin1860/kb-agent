from typing import Dict
from langchain_openai import ChatOpenAI
from .config import LLMProvider, LLMRoles

class LLMRouter:
    """Route LLM calls to the appropriate provider/model based on role."""

    def __init__(self, providers: list[LLMProvider], roles: LLMRoles):
        self._clients: Dict[str, ChatOpenAI] = {}
        for provider in providers:
            for model in provider.models:
                key = f"{provider.name}/{model}"
                api_key_val = provider.api_key.get_secret_value() if provider.api_key else "local"
                if not api_key_val:
                    api_key_val = "local"
                self._clients[key] = ChatOpenAI(
                    api_key=api_key_val,
                    base_url=str(provider.base_url) if provider.base_url else None,
                    model=model,
                    temperature=0.2,
                    timeout=provider.timeout,
                    max_retries=provider.max_retries,
                )
        self._roles = roles

    def get(self, role: str = "base") -> ChatOpenAI:
        """Get LLM client for a specific role."""
        model_key = getattr(self._roles, role, self._roles.base)
        if model_key not in self._clients:
            # Fallback to the first available client if the requested one is missing
            if self._clients:
                return next(iter(self._clients.values()))
            raise ValueError(f"No LLM clients configured. Could not resolve role '{role}'.")
        return self._clients[model_key]

    @property
    def strong(self) -> ChatOpenAI:
        return self.get("strong")

    @property
    def base(self) -> ChatOpenAI:
        return self.get("base")

    @property
    def fast(self) -> ChatOpenAI:
        return self.get("fast") if self._roles.fast else self.get("base")

# Singleton instance initialized lazily
_instance = None

def get_llm_router() -> LLMRouter:
    global _instance
    if _instance is None:
        from .config import settings
        if not settings or not settings.llm_providers or not settings.llm_roles:
            raise ValueError("Settings not loaded or LLM configuration is missing.")
        _instance = LLMRouter(settings.llm_providers, settings.llm_roles)
    return _instance

def reset_llm_router():
    """Reset the router instance, forcing it to reload from settings on next access."""
    global _instance
    _instance = None
