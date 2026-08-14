import json
import logging
import re
from typing import List, Dict, Any
from groq import Groq
from rich.console import Console
from backend.tools.key_manager import key_manager

logger = logging.getLogger("selector")
console = Console()

SELECTOR_SYSTEM_PROMPT = """
You are a Product Shortlist Selector Agent.

Your job is to analyze a pool of verified, priced product candidates and select exactly 3 of them for deep analysis and comparison. Your selection must be intelligent, not arbitrary.

SELECTION CRITERIA (apply in order of importance):

1. BUDGET COMPLIANCE (mandatory): Only select products marked as `within_budget: true`. Never select over-budget products as a primary pick.

2. PRICE-TO-BUDGET FIT: Match the price tier to the user's budget. If the budget is ₹2,00,000, do not select products priced at ₹60,000–₹85,000 when better-priced options (₹1,20,000–₹2,00,000) exist within budget. The user wants to invest their full budget wisely, not get the cheapest option.

3. PRIORITY ALIGNMENT: Prioritize candidates that are most suited to the stated user priority:
   - For "gaming" or "high-refresh gaming": prefer dedicated NVIDIA/AMD GPUs, high TGP variants
   - For "ML" / "AI development" / "CUDA": prefer NVIDIA GPUs with more VRAM (RTX 4060+ or higher), avoid integrated graphics
   - For "video editing" / "3D rendering": prefer NVIDIA/AMD discrete GPUs with good VRAM, not ultrabooks with integrated GPUs
   - For "battery" / "portability": prefer ultrabooks, ARM SoCs (Apple M-series), long battery rated machines
   - For "photography" (phones): prefer higher MP cameras, larger sensors, good ISP

4. DIVERSITY: Avoid selecting 3 variants of the same brand/model family if diverse alternatives exist.

5. RECENCY: Prefer 2024–2026 models over older ones if performance is comparable.

OUTPUT FORMAT:
Return ONLY raw JSON. No markdown, no commentary:

```json
{
  "selected": [
    {
      "name": "Exact Product Name as in input",
      "price_inr": 169990,
      "selection_reason": "One sentence explaining why this product was selected for this user's budget and priority."
    },
    {
      "name": "Exact Product Name 2",
      "price_inr": 219900,
      "selection_reason": "..."
    },
    {
      "name": "Exact Product Name 3",
      "price_inr": 139990,
      "selection_reason": "..."
    }
  ],
  "excluded_summary": "Brief note on why other candidates were excluded."
}
```

CRITICAL: The "name" field MUST exactly match one of the candidate names provided in the input. Do not invent or paraphrase names.
"""


def clean_json_response(raw_text: str) -> str:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def ensure_dict(parsed: Any) -> Dict[str, Any]:
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
        return parsed[0]
    return {}


def run_selector(
    priced_candidates: List[Dict[str, Any]],
    budget: int,
    priority: str,
    category: str,
    user_prompt: str
) -> List[str]:
    """
    LLM Selector Agent: intelligently picks the best 3 product candidates
    from a priced pool for deep analysis.

    Args:
        priced_candidates: List of dicts with keys: name, price_inr, formatted, within_budget
        budget: User's stated budget in INR (or None)
        priority: User's stated priority (e.g., 'ML', 'gaming', 'video editing')
        category: 'laptop' or 'phone'
        user_prompt: Original user query for context

    Returns:
        List of 3 selected product name strings (exact match from input candidates)
    """
    logger.info(f"Selector agent running for priority='{priority}', budget={budget}, candidates={[p['name'] for p in priced_candidates]}")

    # Prepare candidate data for LLM
    candidates_payload = []
    for p in priced_candidates:
        candidates_payload.append({
            "name": p["name"],
            "price_inr": p.get("price_inr"),
            "formatted_price": p.get("formatted", "N/A"),
            "within_budget": p.get("within_budget", False)
        })

    input_payload = {
        "user_prompt": user_prompt,
        "category": category,
        "priority": priority,
        "budget_inr": budget,
        "candidate_pool": candidates_payload
    }

    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SELECTOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"Candidate Pool:\n{json.dumps(input_payload, indent=2)}"}
            ],
            temperature=0.15,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    try:
        raw_out = key_manager.execute_groq(_call_groq)
        cleaned = clean_json_response(raw_out)
        parsed = ensure_dict(json.loads(cleaned))
        selected_list = parsed.get("selected", [])
        excluded_note = parsed.get("excluded_summary", "")

        # Validate and extract names — ensure they match actual candidate names
        candidate_names = {p["name"] for p in priced_candidates}
        selected_names = []
        rank = 1
        for item in selected_list:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
                reason = item.get("selection_reason", "")
                if name in candidate_names:
                    selected_names.append(name)
                    console.print(f"    [bold cyan]#{rank}[/bold cyan] [green]{name}[/green] — [dim]{reason}[/dim]")
                    logger.info(f"  Selector picked: '{name}' — {reason}")
                    rank += 1
                else:
                    logger.warning(f"  Selector returned unknown name '{name}', skipping.")

        if excluded_note:
            console.print(f"    [dim]  ↳ Excluded: {excluded_note}[/dim]")
            logger.info(f"  Excluded: {excluded_note}")

        if len(selected_names) >= 2:
            return selected_names[:3]

    except Exception as e:
        logger.error(f"Selector agent failed: {e}")
        console.print(f"    [red]  ⚠ Selector agent error: {e}[/red]")

    # Fallback: return top within-budget candidates sorted by descending price
    logger.warning("Selector agent fallback: using price-descending sort.")
    console.print("    [yellow]  ⟳ Fallback: using price-descending sort on within-budget candidates.[/yellow]")
    within_budget = sorted(
        [p for p in priced_candidates if p.get("within_budget")],
        key=lambda x: x.get("price_inr") or 0,
        reverse=True
    )
    return [p["name"] for p in within_budget[:3]]
