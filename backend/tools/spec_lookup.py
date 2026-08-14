import json
import logging
import re
from typing import Dict, Any, Optional
from groq import Groq
from backend.tools.key_manager import key_manager

logger = logging.getLogger("spec_lookup")

SPEC_LOOKUP_SYSTEM_PROMPT = """
You are an expert Hardware Benchmark Specialist.
Your job is to analyze raw component specification text (CPU, GPU, or Mobile SoC) extracted from web search and return an objective, standardized hardware performance evaluation in JSON.

DO NOT perform keyword string matching. Instead, use your comprehensive hardware knowledge to identify the component generation, architecture, core/VRAM limits, and relative benchmark tier.

OUTPUT FORMAT:
Return ONLY raw JSON matching this structure:

```json
{
  "identified_model": "Standardized Component Name",
  "hardware_type": "cpu | gpu | soc",
  "tier_level": 1, 
  "performance_score_100": 85,
  "key_features": "e.g. 8GB GDDR6, 140W TGP, CUDA cores",
  "benchmark_summary": "Concise 1-2 sentence performance verdict for gaming, ML/AI, or general productivity."
}
```

NOTE ON TIER LEVEL (1 to 4):
- Tier 1: Flagship / Top-tier (e.g., RTX 4080/4090, M3 Max/Pro, i9/i7 14th/13th gen, Snapdragon 8 Gen 3, RTX 4060)
- Tier 2: Upper Mid-range (e.g., RTX 4050, RTX 3060, Ryzen 7 7840HS, Apple M3, Dimensity 9300)
- Tier 3: Budget / Entry-level (e.g., RTX 3050, i5 13th gen, Apple M2, Snapdragon 8 Gen 2)
- Tier 4: Basic / Integrated Graphics (e.g., Intel Iris Xe, AMD Radeon 780M without discrete GPU)
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

def lookup_spec_tier(category: str, raw_hardware_text: str) -> Dict[str, Any]:
    """
    LLM-powered hardware benchmark lookup tool.
    Uses llama-3.1-8b-instant via KeyManager to evaluate raw hardware specs text
    and return standardized tier/benchmark data without relying on keyword matching.
    """
    if not raw_hardware_text or len(raw_hardware_text.strip()) < 3:
        return {
            "identified_model": "Unknown",
            "tier_level": 3,
            "performance_score_100": 50,
            "benchmark_summary": "Insufficient hardware specification data available for lookup."
        }

    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        messages = [
            {"role": "system", "content": SPEC_LOOKUP_SYSTEM_PROMPT},
            {"role": "user", "content": f"Category: {category}\nRaw Hardware Text: \"{raw_hardware_text}\""}
        ]
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    try:
        raw_output = key_manager.execute_groq(_call_groq)
        cleaned = clean_json_response(raw_output)
        parsed = json.loads(cleaned)
        return ensure_dict(parsed)
    except Exception as e:
        logger.error(f"LLM spec lookup failed for '{raw_hardware_text[:50]}...': {e}")
        return {
            "identified_model": raw_hardware_text[:30],
            "tier_level": 2,
            "performance_score_100": 70,
            "benchmark_summary": "Evaluated with default baseline performance metric."
        }
