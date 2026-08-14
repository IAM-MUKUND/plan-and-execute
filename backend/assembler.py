import json
import logging
from groq import Groq
from backend.state import AppState
from backend.tools.key_manager import key_manager

logger = logging.getLogger("assembler")

ASSEMBLER_SYSTEM_PROMPT = """
You are the Lead Hardware Recommendation Assembler.
Your job is to synthesize all collected product data into a comprehensive, professional final recommendation report.

The input contains two sections:
- `selected_products_for_analysis`: The top 3 products chosen for deep analysis (full specs, pricing, performance data).
- `other_candidates_considered`: Other products that were priced but not selected for deep analysis. Show these in a brief summary table only.

CRITICAL BUDGET INSTRUCTIONS:
1. Only recommend products from `selected_products_for_analysis` as the primary choices.
2. Clearly mark any product whose price exceeds the stated budget as OVER BUDGET.
3. If a product's price is unknown, note the uncertainty — do not assume it's within budget.

REPORT FORMAT (markdown, clean and professional):

1. **Executive Summary / Clear Winner Verdict**: Name the best product from the selected 3 and explain why in 3-4 sentences, citing GPU/CPU tier, budget utilisation, and priority fit.
2. **Structured Comparison Table**: Compare the 3 selected products on key specs relevant to the user's priority (GPU, CPU, RAM, display, price, budget compliance, performance score).
3. **Detailed Breakdown per Product** (for each of the 3 selected only):
   - Pros, Cons, Price in India, Performance Score, Priority Verdict
4. **Other Candidates Considered**: A brief bullet list of the non-selected candidates with their price and budget status (from `other_candidates_considered`).
5. **Final Buying Advice**: Practical 2-3 sentence recommendation tailored to the user's priority and budget.
"""

def assemble_final_recommendation(state: AppState) -> str:
    """
    Synthesizes the final recommendation report from AppState using llama-3.3-70b-versatile via KeyManager.
    Pre-computes budget compliance for each product before sending to the LLM assembler.
    """
    logger.info(f"Assembling final recommendation for prompt: '{state.user_prompt}'")

    # ─── Split products into selected (deep analysis) vs. rest (brief note) ──────
    # Only the selector's top-3 get full specs/pricing/performance breakdown.
    # All other priced candidates are surfaced as a brief "also considered" list.
    selected_names_set = set(state.target_products)

    selected_products = {}
    other_candidates = {}

    for name, pstate in state.products.items():
        price_inr = None
        budget_status = "unknown"

        if pstate.pricing:
            price_inr = pstate.pricing.get("price_inr")
            if price_inr and isinstance(price_inr, (int, float)):
                if state.budget:
                    if price_inr <= state.budget:
                        budget_status = "within_budget"
                    else:
                        overage = price_inr - state.budget
                        budget_status = f"OVER BUDGET by ₹{overage:,.0f}"
                else:
                    budget_status = "no_budget_specified"

        entry = {
            "specs": pstate.specs,
            "pricing": pstate.pricing,
            "performance": pstate.performance,
            "budget_compliance": budget_status,
            "price_inr": price_inr
        }

        if pstate.name in selected_names_set:
            selected_products[pstate.name] = entry
        else:
            # Brief entry for non-selected candidates (pricing only, no specs/perf)
            other_candidates[pstate.name] = {
                "price_inr": price_inr,
                "formatted_price": pstate.pricing.get("formatted_price", "N/A") if pstate.pricing else "N/A",
                "budget_compliance": budget_status
            }

    state_context = {
        "user_prompt": state.user_prompt,
        "category": state.category,
        "stated_priority": state.priority,
        "budget_inr": state.budget,
        "selected_products_for_analysis": selected_products,
        "other_candidates_considered": other_candidates
    }

    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        prompt_content = f"Complete System State Data:\n{json.dumps(state_context, indent=2)}"
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ASSEMBLER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.3,
            max_tokens=1800
        )
        return response.choices[0].message.content

    try:
        recommendation_report = key_manager.execute_groq(_call_groq)
    except Exception as e:
        logger.error(f"Assembler failed to generate recommendation: {e}")
        recommendation_report = (
            f"## Final Recommendation Report (Fallback)\n\n"
            f"Failed to generate full synthesis report due to error: {e}\n\n"
            f"### Collected Products Data:\n```json\n{json.dumps(products_summary, indent=2)}\n```"
        )

    # Mark the final generate_recommendation step as completed in state
    for task in state.plan:
        if task.step_type == "generate_recommendation":
            state.mark_step_completed(task.id, result=recommendation_report[:200] + "...")

    return recommendation_report
