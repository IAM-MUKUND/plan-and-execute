import json
import logging
import re
from typing import Dict, Any, List
from groq import Groq
from backend.state import AppState, SubTask
from backend.tools.key_manager import key_manager

logger = logging.getLogger("planner")

PLANNER_SYSTEM_PROMPT = """
You are the Lead Technical Planner for a Product Comparison Agent.
Your task is to analyze the user's natural language request and decompose it into a structured, execution-ready JSON plan.

### RULES FOR PLANNING:
1. Product Category: Detect if the user is comparing 'laptop' or 'phone'. Default to 'laptop'.
2. User Priority: Identify the primary requirement (e.g., 'ML' / 'AI development', 'gaming', 'photography', 'battery', 'budget', or 'general').
3. Budget: Extract numeric budget value if present (e.g., 90000 for "90,000" or "90k", 150000 for "1,50,000" or "1.5 lakh"), otherwise null.
4. Target Products: ONLY populate `target_products` with real product names if the user explicitly names them (e.g. "Compare iPhone 15 and Samsung S24"). If the user says "any laptop", "best phone", "recommend me", or similar open-ended requests, you MUST leave `target_products` as an empty list [].

### CRITICAL RULE — OPEN-ENDED QUERIES:
If the user has NOT named specific products, ALL `collect_specs`, `collect_pricing`, and `analyze_performance` subtask steps MUST have `"target_product": null`. The `identify_products` step will dynamically discover real candidates from the web at runtime using the budget and priority as search context.

NEVER fill in product model names from your own training knowledge when the user has not named products — these will be outdated and may be out-of-budget.

### SUBTASK TYPES:
You MUST decompose the request into numbered subtasks using ONLY these allowed `step_type` values:
- `identify_products`: Identify/confirm candidate products to compare. (depends_on: [])
- `collect_specs`: Collect technical specifications for products. (depends_on: [id of identify_products])
- `collect_pricing`: Collect pricing details for products. (depends_on: [id of identify_products])
- `analyze_performance`: Analyze performance using collected specs. (MUST depend on the collect_specs step ID)
- `generate_recommendation`: Synthesize final prioritized recommendation across all products. (MUST depend on all previous spec, pricing, and performance step IDs)

### EXAMPLE 1 — Explicit Product Names:
User: "Compare iPhone 15 and Samsung Galaxy S24 for photography"
→ target_products: ["iPhone 15", "Samsung Galaxy S24"]
→ Each subtask has the explicit target_product set.

### EXAMPLE 2 — Open-Ended Query (NO specific products named):
User: "Recommend the best laptop under ₹1,50,000 for AI development"
→ target_products: []
→ ALL collect_specs, collect_pricing, analyze_performance steps have `"target_product": null`
→ The identify_products step will discover real in-budget models at runtime.

### OUTPUT FORMAT:
You MUST output ONLY raw valid JSON. No markdown, no commentary:

For open-ended queries:
```json
{
  "category": "laptop",
  "priority": "ML",
  "budget": 150000,
  "target_products": [],
  "plan": [
    {"id": 1, "step_type": "identify_products", "target_product": null, "description": "Discover top laptops for ML under ₹1,50,000 via web search", "depends_on": []},
    {"id": 2, "step_type": "collect_specs", "target_product": null, "description": "Collect specifications for identified laptops", "depends_on": [1]},
    {"id": 3, "step_type": "collect_pricing", "target_product": null, "description": "Collect pricing for identified laptops", "depends_on": [1]},
    {"id": 4, "step_type": "analyze_performance", "target_product": null, "description": "Analyze performance of identified laptops for ML priority", "depends_on": [2]},
    {"id": 5, "step_type": "generate_recommendation", "target_product": null, "description": "Synthesize final recommendation for ML under ₹1,50,000", "depends_on": [2, 3, 4]}
  ]
}
```

For explicit product queries:
```json
{
  "category": "phone",
  "priority": "photography",
  "budget": null,
  "target_products": ["iPhone 15", "Samsung Galaxy S24"],
  "plan": [
    {"id": 1, "step_type": "identify_products", "target_product": null, "description": "Confirm products: iPhone 15, Samsung Galaxy S24", "depends_on": []},
    {"id": 2, "step_type": "collect_specs", "target_product": "iPhone 15", "description": "Collect specs for iPhone 15", "depends_on": [1]},
    {"id": 3, "step_type": "collect_specs", "target_product": "Samsung Galaxy S24", "description": "Collect specs for Samsung Galaxy S24", "depends_on": [1]},
    {"id": 4, "step_type": "collect_pricing", "target_product": "iPhone 15", "description": "Collect pricing for iPhone 15", "depends_on": [1]},
    {"id": 5, "step_type": "collect_pricing", "target_product": "Samsung Galaxy S24", "description": "Collect pricing for Samsung Galaxy S24", "depends_on": [1]},
    {"id": 6, "step_type": "analyze_performance", "target_product": "iPhone 15", "description": "Analyze iPhone 15 camera performance", "depends_on": [2]},
    {"id": 7, "step_type": "analyze_performance", "target_product": "Samsung Galaxy S24", "description": "Analyze Samsung Galaxy S24 camera performance", "depends_on": [3]},
    {"id": 8, "step_type": "generate_recommendation", "target_product": null, "description": "Synthesize final photography recommendation", "depends_on": [2, 3, 4, 5, 6, 7]}
  ]
}
```
"""

def clean_json_response(raw_text: str) -> str:
    """Strip markdown code fences and whitespace from LLM output."""
    cleaned = raw_text.strip()
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()

def generate_plan(user_prompt: str) -> AppState:
    """
    Calls Groq (llama-3.3-70b-versatile) via KeyManager to convert user_prompt into AppState plan.
    Includes auto-retry safety net on malformed JSON.
    """
    def _call_groq(api_key: str, extra_instruction: str = ""):
        client = Groq(api_key=api_key)
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"User Request: \"{user_prompt}\"{extra_instruction}"}
        ]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    # Attempt 1
    raw_output = key_manager.execute_groq(_call_groq)
    cleaned_output = clean_json_response(raw_output)

    parsed_data = None
    try:
        parsed_data = json.loads(cleaned_output)
    except json.JSONDecodeError as e:
        logger.warning(f"Planner JSONDecodeError on attempt 1: {e}. Retrying with strict JSON instruction...")
        # Attempt 2 (Retry)
        retry_instruction = "\n\nCRITICAL ERROR: Your previous response was invalid JSON. Output ONLY raw JSON matching the required schema!"
        raw_output_retry = key_manager.execute_groq(lambda k: _call_groq(k, extra_instruction=retry_instruction))
        cleaned_retry = clean_json_response(raw_output_retry)
        parsed_data = json.loads(cleaned_retry)

    # Build Pydantic AppState
    category = parsed_data.get("category", "laptop")
    priority = parsed_data.get("priority", "general")
    budget = parsed_data.get("budget")
    target_products = parsed_data.get("target_products", [])
    
    subtasks = []
    for step in parsed_data.get("plan", []):
        subtasks.append(SubTask(
            id=step["id"],
            step_type=step["step_type"],
            target_product=step.get("target_product"),
            description=step["description"],
            depends_on=step.get("depends_on", []),
            status="pending"
        ))

    app_state = AppState(
        user_prompt=user_prompt,
        category=category,
        priority=priority,
        budget=budget,
        target_products=target_products,
        plan=subtasks
    )

    # Initialize product states in AppState
    for prod_name in target_products:
        app_state.get_or_create_product(prod_name)

    return app_state
