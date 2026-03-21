import pytest
from pydantic import SecretStr, HttpUrl
from kb_agent.config import _migrate_legacy_llm_config, LLMProvider, LLMRoles, Settings
from kb_agent.llm_router import LLMRouter

def test_config_migration():
    data = {
        "llm_api_key": "old-key",
        "llm_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4"
    }
    
    _migrate_legacy_llm_config(data)
    
    assert "llm_providers" in data
    assert len(data["llm_providers"]) == 1
    
    provider = data["llm_providers"][0]
    assert provider["name"] == "default"
    assert provider["api_key"] == "old-key"
    assert provider["base_url"] == "https://api.openai.com/v1"
    assert provider["models"] == ["gpt-4"]
    
    assert "llm_roles" in data
    roles = data["llm_roles"]
    assert roles["strong"] == "default/gpt-4"
    assert roles["base"] == "default/gpt-4"
    assert roles["fast"] == "default/gpt-4"

def test_llm_router_dispatch():
    provider1 = LLMProvider(
        name="openai",
        base_url=HttpUrl("https://api.openai.com/v1"),
        api_key=SecretStr("key1"),
        models=["gpt-4", "gpt-3.5-turbo"]
    )
    provider2 = LLMProvider(
        name="local",
        base_url=HttpUrl("http://localhost:11434/v1"),
        api_key=SecretStr(""),
        models=["llama3"]
    )
    
    roles = LLMRoles(
        strong="openai/gpt-4",
        base="local/llama3",
        fast="openai/gpt-3.5-turbo"
    )
    
    router = LLMRouter(providers=[provider1, provider2], roles=roles)
    
    strong_llm = router.get("strong")
    assert strong_llm.model_name == "gpt-4"
    
    base_llm = router.get("base")
    assert base_llm.model_name == "llama3"
    
    fast_llm = router.get("fast")
    assert fast_llm.model_name == "gpt-3.5-turbo"
    
    # Test property accessors
    assert router.strong.model_name == "gpt-4"
    assert router.base.model_name == "llama3"
    assert router.fast.model_name == "gpt-3.5-turbo"
    
def test_llm_router_fallback():
    # Test that missing requested roles fall back correctly
    provider = LLMProvider(
        name="openai",
        base_url=HttpUrl("https://api.openai.com/v1"),
        api_key=SecretStr("key"),
        models=["gpt-4"]
    )
    roles = LLMRoles(
        strong="openai/gpt-4",
        base="openai/gpt-4"
        # fast is omitted (defaults to None in model)
    )
    
    router = LLMRouter(providers=[provider], roles=roles)
    
    # Should fallback to base if fast is not set
    assert router.fast.model_name == "gpt-4"
