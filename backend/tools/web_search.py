import logging
from typing import Dict, Any, List
from tavily import TavilyClient
from backend.tools.key_manager import key_manager

logger = logging.getLogger("web_search")

def search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Perform a search query using Tavily API with automatic key rotation.
    Returns a list of dicts with title, content, url, score.
    """
    def _call_tavily(api_key: str):
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "url": item.get("url", ""),
                "score": item.get("score", 0.0)
            })
        return results

    try:
        return key_manager.execute_tavily(_call_tavily)
    except Exception as e:
        logger.error(f"Tavily search failed for query '{query}': {e}")
        return []
