import json
import logging
import re
from typing import Dict, Any
from groq import Groq
from backend.state import AppState
from backend.tools.spec_lookup import lookup_spec_tier
from backend.tools.key_manager import key_manager

logger = logging.getLogger("performance_executor")

PERFORMANCE_ANALYSIS_PROMPT = """
You are a High-Performance Hardware Evaluation Agent.
Your job is to analyze pre-extracted technical specifications and hardware benchmark tier data for a product, and synthesize a qualitative performance verdict tailored to the user's priority requirement.

CRITICAL INSTRUCTION:
Do NOT trigger new search queries for raw specs. Rely ONLY on the provided specs and tier lookup data in the user prompt.

OUTPUT FORMAT:
Return ONLY raw JSON matching this structure:

```json
{
  "qualitative_score_100": 88,
  "priority_focus": "ML",
  "priority_verdict": "Detailed evaluation explaining how well this hardware handles the user's specific priority (e.g., ML VRAM capacity, gaming FPS, or camera ISP processing).",
  "strengths": ["Strength 1", "Strength 2"],
  "limitations": ["Limitation 1", "Limitation 2"],
  "thermal_efficiency_notes": "Thermals, power consumption, and throttling evaluation."
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

def run_performance_executor(product_name: str, state: AppState) -> Dict[str, Any]:
    """
    Executes Performance Analysis agent for `product_name`.
    Model: llama-3.3-70b-versatile via KeyManager.
    
    IMPORTANT: Reuses state.products[name].specs already collected in Step 1/2.
    Does NOT invoke web search again. Uses spec_lookup.py LLM tool for tier grounding.
    """
    logger.info(f"Running Performance Executor for: '{product_name}' (priority: {state.priority})")
    
    # 1. Fetch pre-collected specs from AppState
    product_state = state.get_or_create_product(product_name)
    collected_specs = product_state.specs or {}
    
    if not collected_specs or "error" in collected_specs:
        logger.warning(f"No valid specs found in state for '{product_name}'. Running with basic product name context.")

    # 2. Extract main hardware component text for LLM spec lookup tool
    gpu_or_cpu_text = collected_specs.get("gpu") or collected_specs.get("processor") or collected_specs.get("processor_chipset") or product_name
    
    # 3. Ground hardware performance via LLM tool call (No string keyword matching!)
    tier_grounding = lookup_spec_tier(category=state.category, raw_hardware_text=gpu_or_cpu_text)

    # 4. Synthesize performance evaluation with llama-3.3-70b-versatile
    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        prompt_content = (
            f"Product Name: {product_name}\n"
            f"Category: {state.category}\n"
            f"User Stated Priority: {state.priority}\n"
            f"Collected Technical Specs (From State): {json.dumps(collected_specs, indent=2)}\n"
            f"Hardware Tier Grounding Data: {json.dumps(tier_grounding, indent=2)}"
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": PERFORMANCE_ANALYSIS_PROMPT},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    try:
        raw_out = key_manager.execute_groq(_call_groq)
        cleaned = clean_json_response(raw_out)
        parsed = json.loads(cleaned)
        perf_data = ensure_dict(parsed)
        perf_data["tier_grounding"] = tier_grounding
        perf_data["specs_reused_from_state"] = True
    except Exception as e:
        logger.error(f"Performance analysis failed for '{product_name}': {e}")
        perf_data = {"error": str(e), "product": product_name, "tier_grounding": tier_grounding}

    state.update_product_performance(product_name, perf_data)
    return perf_data
