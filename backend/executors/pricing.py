import json
import logging
import re
from typing import Dict, Any
from groq import Groq
from backend.state import AppState
from backend.tools.web_search import search
from backend.tools.key_manager import key_manager

logger = logging.getLogger("pricing_executor")

PRICING_EXTRACTION_PROMPT = """
You are a Product Pricing Extractor Agent.
Your job is to analyze search snippet data for a product in India (INR ₹) and extract structured pricing details.

OUTPUT FORMAT:
Return ONLY raw JSON matching this structure:

```json
{
  "price_inr": 84990,
  "formatted_price": "₹84,990",
  "currency": "INR",
  "source_platform": "e.g. Amazon India, Flipkart, Official Store",
  "availability": "in_stock | out_of_stock | unknown",
  "notes": "Short note on offers/variants if available"
}
```
"""

def clean_json_response(raw_text: str) -> str:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()

def ensure_dict(parsed: Any) -> Dict[str, Any]:
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        if len(parsed) > 0 and isinstance(parsed[0], dict):
            return parsed[0]
    return {}

def run_pricing_executor(product_name: str, state: AppState) -> Dict[str, Any]:
    """
    Executes Pricing Collector agent for `product_name`.
    Uses Tavily search + llama-3.1-8b-instant via KeyManager to populate state.products[name].pricing.
    """
    logger.info(f"Running Pricing Executor for: '{product_name}' (budget: {state.budget})")
    
    query = f"{product_name} price in India buy online price rupees"
    search_results = search(query=query, max_results=3)
    
    snippets_text = ""
    source_url = ""
    for idx, res in enumerate(search_results, 1):
        if idx == 1:
            source_url = res.get("url", "")
        snippets_text += f"\n--- Source {idx} ({res['url']}) ---\nTitle: {res['title']}\nSnippet: {res['content']}\n"

    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        prompt_content = f"Product Name: {product_name}\nTarget Market: India (INR)\n\nWeb Search Snippets:\n{snippets_text}"
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": PRICING_EXTRACTION_PROMPT},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    try:
        raw_out = key_manager.execute_groq(_call_groq)
        cleaned = clean_json_response(raw_out)
        parsed = json.loads(cleaned)
        pricing_data = ensure_dict(parsed)
        pricing_data["source_url"] = source_url
        
        # Calculate budget compliance if budget is set
        price_num = pricing_data.get("price_inr")
        if state.budget and isinstance(price_num, (int, float)):
            pricing_data["within_budget"] = price_num <= state.budget
            pricing_data["budget_delta"] = state.budget - price_num
        else:
            pricing_data["within_budget"] = None
    except Exception as e:
        logger.error(f"Pricing extraction failed for '{product_name}': {e}")
        pricing_data = {"error": str(e), "product": product_name}

    state.update_product_pricing(product_name, pricing_data)
    return pricing_data
