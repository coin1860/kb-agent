from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

class BaseConnector(ABC):
    """Abstract base class for data connectors."""

    @abstractmethod
    def fetch_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetches data based on a query or identifier.

        Args:
            query (str): The search query or ID (e.g., Jira ID, Confluence Page ID).

        Returns:
            List[Dict[str, Any]]: A list of documents/data found.
                                  Each dict should ideally contain 'id', 'title', 'content', 'metadata'.
        """
        pass

    @abstractmethod
    def fetch_all(self) -> List[Dict[str, Any]]:
        """
        Fetches all available data (for initial indexing/caching).
        """
        pass
