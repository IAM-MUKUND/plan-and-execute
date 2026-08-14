import sys
import os

# Add CAT-1 to python path so backend package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tools.key_manager import key_manager
from backend.tools.web_search import search

def main():
    print("=== Tavily Search Smoke Test with KeyManager ===")
    print(f"Loaded {len(key_manager.tavily_keys)} Tavily API keys.")
    print(f"Current active key index: {key_manager.tavily_index}")

    query = "Apple MacBook Air M3 specs"
    print(f"\nExecuting search query: '{query}'...")

    try:
        results = search(query=query, max_results=3)
        print(f"\n[SUCCESS] Retrived {len(results)} search results:")
        for idx, res in enumerate(results, 1):
            print(f"\nResult #{idx}:")
            print(f"  Title : {res['title']}")
            print(f"  URL   : {res['url']}")
            print(f"  Snippet: {res['content'][:150]}...")
    except Exception as e:
        print(f"\n[FAILURE] Tavily API search failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
