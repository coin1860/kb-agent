import os
import json
from pathlib import Path
from pydantic import BaseModel, Field, SecretStr, HttpUrl
from typing import Optional, Dict, Any

CONFIG_DIR = Path.home() / ".kb-agent"
CONFIG_FILE = CONFIG_DIR / "kb-agent.json"
OLD_ENV_FILE = Path.home() / ".kb_agent" / ".env"
LOCAL_ENV_FILE = Path(".env")

# Removed hardcoded DEFAULTS as per user request.
# The user's .env file or the TUI settings page will be the sole source of configuration truths.

class Settings(BaseModel):
    # LLM Configuration
    llm_api_key: Optional[SecretStr] = Field(None, description="API Key for the LLM provider")
    llm_base_url: Optional[HttpUrl] = Field(None, description="Base URL for the LLM API")
    llm_model: Optional[str] = Field(None, description="Model name to use for chat completion")
    # Embedding Configuration
    embedding_url: Optional[str] = Field(None, description="URL for the Embedding API. Empty to use local models.")
    embedding_model: Optional[str] = Field(None, description="Model name for embeddings.")
    
    # Agent/RAG Configuration
    max_iterations: Optional[int] = Field(None, description="Max iterations for agent RAG loops")
    vector_score_threshold: Optional[float] = Field(0.5, description="Distance threshold for vector search. Also fast-path threshold for vector search auto-approve.")
    auto_approve_max_items: Optional[int] = Field(None, description="Fast-path threshold for few-context auto-approve")
    chunk_max_chars: Optional[int] = Field(800, description="Max characters per chunk for knowledge document splitting")
    chunk_overlap_chars: Optional[int] = Field(200, description="Character overlap between consecutive chunks")
    debug_mode: Optional[bool] = Field(False, description="Enable debug mode to show detailed chunks in the TUI")

    # Paths
    data_folder: Optional[Path] = Field(None, description="Base directory for kb-agent data")
    source_docs_path: Optional[Path] = Field(None, description="Path to read source markdown docs")
    index_path: Optional[Path] = Field(None, description="Path to store processed/indexed docs")
    archive_path: Optional[Path] = Field(None, description="Path to archive processed docs")
    audit_log_path: Optional[Path] = Field(None, description="Path to the audit log file")

    # Proxy
    http_proxy: Optional[HttpUrl] = Field(None, description="HTTP Proxy URL")
    https_proxy: Optional[HttpUrl] = Field(None, description="HTTPS Proxy URL")

    # External Services
    jira_url: Optional[HttpUrl] = Field(None, description="Jira Instance URL")
    jira_token: Optional[SecretStr] = Field(None, description="Jira Personal Access Token / API Token")
    confluence_url: Optional[HttpUrl] = Field(None, description="Confluence Instance URL")
    confluence_token: Optional[SecretStr] = Field(None, description="Confluence Personal Access Token / API Token")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._compute_paths()

    def _compute_paths(self):
        # If data_folder is set, override the other paths if they aren't explicitly provided
        if self.data_folder:
            if not self.source_docs_path:
                self.source_docs_path = self.data_folder / "source"
            if not self.index_path:
                self.index_path = self.data_folder / "index"
            if not self.archive_path:
                self.archive_path = self.data_folder / "archive"
        else:
            # Provide sensible dynamic fallbacks for required paths if data_folder is NOT set
            # and they are missing from the configuration.
            if not self.source_docs_path:
                self.source_docs_path = Path.home() / "data" / "markdown_docs"
            if not self.index_path:
                self.index_path = Path.home() / ".kb-agent" / "index"
            if not self.archive_path:
                self.archive_path = Path.home() / ".kb-agent" / "archive"
                
        if not self.audit_log_path:
            self.audit_log_path = Path("audit.log")

    # Backward compatibility alias
    @property
    def docs_path(self):
        return self.index_path

# Global settings instance
settings: Optional[Settings] = None

def _read_env_file(filepath: Path) -> Dict[str, Any]:
    """Helper to parse an env file into a dictionary of KB_AGENT_ settings."""
    data = {}
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # Strip prefix for the model
                if key.startswith("KB_AGENT_"):
                    model_key = key[9:].lower()
                    data[model_key] = value
    return data

def _get_initial_data() -> Dict[str, Any]:
    """Determine initial configuration data before loading from JSON."""
    data = {}
    
    # 1. Check local .env
    if LOCAL_ENV_FILE.exists():
        env_data = _read_env_file(LOCAL_ENV_FILE)
        data.update(env_data)
        return data
        
    # 2. Check old ~/.kb_agent/.env
    if OLD_ENV_FILE.exists():
        env_data = _read_env_file(OLD_ENV_FILE)
        data.update(env_data)
        
    return data

def load_settings() -> Optional[Settings]:
    """Load settings from JSON, initializing from defaults/.env if JSON doesn't exist."""
    global settings
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = _get_initial_data()
            _save_data(data)
            
        settings = Settings(**data)
        
        # Load proxy env vars if they exist in OS env (as fallback/override)
        if "KB_AGENT_HTTP_PROXY" in os.environ and not settings.http_proxy:
            settings.http_proxy = os.environ["KB_AGENT_HTTP_PROXY"]
        if "KB_AGENT_HTTPS_PROXY" in os.environ and not settings.https_proxy:
            settings.https_proxy = os.environ["KB_AGENT_HTTPS_PROXY"]
            
        # Export max_iterations to env for graph.py to pick up at runtime
        if settings.max_iterations is not None:
            os.environ["KB_AGENT_MAX_ITERATIONS"] = str(settings.max_iterations)
            
        return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        settings = None
        return None

def _save_data(data: Dict[str, Any]):
    """Internal helper to save dict data to JSON."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def save_settings(new_settings: Settings):
    """Save a Settings object to the JSON file."""
    global settings
    
    # Dump to dict, handling secrets correctly (get actual value)
    data = new_settings.model_dump(mode='json')
    
    # We must properly unpack secrets which come out as '**********' in default model_dump
    for field_name, value in new_settings:
        if isinstance(value, SecretStr):
            data[field_name] = value.get_secret_value()
            
    # Clean up None values to keep JSON tidy
    data = {k: v for k, v in data.items() if v is not None}
    
    _save_data(data)
    settings = new_settings

def update_setting(key: str, value: Any):
    """Update a single configuration key in the JSON file."""
    # Read current
    data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
            
    # Update dict
    if value is None:
        if key in data:
            del data[key]
    else:
        # Pydantic Settings expects lowercased keys without KB_AGENT_ prefix
        if key.startswith("KB_AGENT_"):
            key = key[9:].lower()
        data[key] = value
        
    # Save back
    _save_data(data)
    
    # Reload global instance
    load_settings()

# Initial load attempt
load_settings()
