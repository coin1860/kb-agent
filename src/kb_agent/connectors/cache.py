import json
import logging
from typing import Optional, Dict, Any
import kb_agent.config as config

logger = logging.getLogger("kb_agent_audit")

class APICache:
    """Manages persistent file-based caching for API responses."""
    
    def __init__(self):
        # Rely on config.settings.cache_path which handles the data_folder fallback logic
        settings = config.settings
        self.cache_root = settings.cache_path if settings and settings.cache_path else None

    def _get_cache_dir(self, service: str, entity_id: str):
        if not self.cache_root:
            from pathlib import Path
            return Path.home() / ".kb-agent" / "cache" / service / str(entity_id)
        return self.cache_root / service / str(entity_id)

    def read(self, service: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Attempt to read from cache. Return the dict if found, else None."""
        cache_dir = self._get_cache_dir(service, entity_id)
        main_file = cache_dir / "main.json"
        
        if main_file.exists():
            try:
                with open(main_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"Cache hit: {service}/{entity_id}")
                return data
            except Exception as e:
                logger.error(f"Failed to read cache at {main_file}: {e}")
        
        logger.debug(f"Cache miss: {service}/{entity_id} → fetching from API")
        return None

    def write(self, service: str, entity_id: str, data: Dict[str, Any]):
        """Write formatted API payload to cache dict to main.json."""
        cache_dir = self._get_cache_dir(service, entity_id)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            main_file = cache_dir / "main.json"
            
            with open(main_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Wrote cache for {service}/{entity_id}")
        except Exception as e:
            logger.error(f"Failed to write cache for {service}/{entity_id}: {e}")

