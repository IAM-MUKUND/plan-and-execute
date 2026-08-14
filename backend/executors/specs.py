import json
import logging
import re
from typing import Dict, Any
from groq import Groq
from backend.state import AppState
from backend.tools.web_search import search
from backend.tools.key_manager import key_manager

logger = logging.getLogger("specs_executor")

SPECS_EXTRACTION_PROMPT = """
You are a Technical Specification Extractor Agent.
Your job is to analyze web search snippet data about a product and extract precise technical specifications into a clean, structured JSON object.

OUTPUT FORMAT:
Return ONLY raw JSON matching this structure:

For Laptops:
```json
{
  "processor": "Exact CPU Model Name",
  "gpu": "Exact GPU Model Name (Discrete or Integrated)",
  "ram": "RAM capacity & type (e.g. 16GB DDR5)",
  "storage": "Storage capacity & type (e.g. 512GB NVMe SSD)",
  "display": "Display size, resolution, refresh rate",
  "battery": "Battery capacity (Wh or mAh)",
  "os": "Operating System",
  "weight_kg": "Weight in kg if available"
}
```

For Phones:
```json
{
  "processor_chipset": "Exact Mobile SoC/Chipset Name",
  "ram": "RAM capacity",
  "storage": "Storage capacity",
  "display": "Display type, size, refresh rate",
  "camera_setup": "Main rear & front camera specs",
  "battery_mah": "Battery capacity in mAh",
  "charging_speed": "Charging wattage",
  "os": "Operating System"
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

def run_specs_executor(product_name: str, state: AppState) -> Dict[str, Any]:
    """
    Executes Specs Collector agent for `product_name`.
    Uses Tavily search + llama-3.1-8b-instant via KeyManager to populate state.products[name].specs.
    """
    logger.info(f"Running Specs Executor for: '{product_name}' (category: {state.category})")
    
    query = f"{product_name} {state.category} official technical specifications processor GPU RAM display battery"
    search_results = search(query=query, max_results=3)
    
    snippets_text = ""
    for idx, res in enumerate(search_results, 1):
        snippets_text += f"\n--- Source {idx} ({res['url']}) ---\nTitle: {res['title']}\nSnippet: {res['content']}\n"

    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        prompt_content = f"Product Name: {product_name}\nCategory: {state.category}\n\nWeb Search Snippets:\n{snippets_text}"
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SPECS_EXTRACTION_PROMPT},
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
        specs_data = ensure_dict(parsed)
    except Exception as e:
        logger.error(f"Specs extraction failed for '{product_name}': {e}")
        specs_data = {"error": str(e), "product": product_name}

    state.update_product_specs(product_name, specs_data)
    return specs_data
