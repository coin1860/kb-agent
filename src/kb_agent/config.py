from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, HttpUrl
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    # LLM Configuration
    llm_api_key: SecretStr = Field(..., description="API Key for the LLM provider")
    llm_base_url: HttpUrl = Field(..., description="Base URL for the LLM API")
    llm_model: str = Field("gpt-4", description="Model name to use for chat completion")
    embedding_model: str = Field("all-MiniLM-L6-v2", description="Embedding model name")

    # Paths
    source_docs_path: Path = Field(default=Path.home() / "data" / "markdown_docs", description="Path to read source markdown docs")
    index_path: Path = Field(default=Path.home() / ".kb_agent" / "index", description="Path to store processed/indexed docs")

    # Backward compatibility alias
    @property
    def docs_path(self):
        return self.index_path

    audit_log_path: Path = Field(default=Path("audit.log"), description="Path to the audit log file")

    # Proxy
    http_proxy: Optional[HttpUrl] = Field(None, description="HTTP Proxy URL")
    https_proxy: Optional[HttpUrl] = Field(None, description="HTTPS Proxy URL")

    # External Services (Optional for now, but good to have placeholders)
    jira_url: Optional[HttpUrl] = Field(None, description="Jira Instance URL")
    confluence_url: Optional[HttpUrl] = Field(None, description="Confluence Instance URL")

    model_config = SettingsConfigDict(
        env_prefix="KB_AGENT_",
        env_file=(".env", str(Path.home() / ".kb_agent" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Global settings instance
settings: Optional[Settings] = None

def load_settings():
    global settings
    try:
        settings = Settings()
        return settings
    except Exception as e:
        settings = None
        return None

# Initial load attempt
load_settings()
