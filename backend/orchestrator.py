import json
import logging
import re
from typing import List, Dict, Any, Optional
from groq import Groq
from rich.console import Console
from rich.panel import Panel

from backend.state import AppState, SubTask
from backend.executors.specs import run_specs_executor
from backend.executors.pricing import run_pricing_executor
from backend.executors.performance import run_performance_executor
from backend.tools.web_search import search
from backend.tools.key_manager import key_manager
from backend.tools.selector import run_selector

logger = logging.getLogger("orchestrator")
console = Console()

IDENTIFY_PRODUCTS_PROMPT = """
You are a Product Model Extractor Agent.
Your job is to analyze web search snippet data for an open-ended query and extract up to 8 real, specific, brand-and-model product names that are currently available in India and likely within the stated budget.

RULES:
1. Extract REAL, specific product model names (e.g., "Lenovo Legion Slim 5", "ASUS TUF Gaming A15", "Acer Nitro 16", "Samsung Galaxy S24", "iPhone 15").
2. DO NOT return merchant names, web domain names, or generic article headlines (e.g., NEVER return "Amazon.in", "Flipkart", "Best Laptops Under 100000", "Top 5 Laptops").
3. Prefer currently available models (2023-2026). Avoid discontinued or extremely old models.
4. Include up to 8 candidates — more is better so we can verify pricing and filter down.

OUTPUT FORMAT:
Return ONLY raw JSON matching this structure:

```json
{
  "products": ["Model Name 1", "Model Name 2", "Model Name 3", "Model Name 4", "Model Name 5", "Model Name 6", "Model Name 7", "Model Name 8"]
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


def resolve_target_product_names(task: SubTask, state: AppState) -> List[str]:
    """
    Returns the list of product names targeted by a subtask.
    If task.target_product is specified, returns [task.target_product].
    Otherwise returns all products registered in state.target_products.
    """
    if task.target_product and task.target_product.strip():
        return [task.target_product.strip()]
    if state.target_products:
        return state.target_products
    return list(state.products.keys())


def _build_search_query(state: AppState, attempt: int = 0) -> str:
    """
    Builds a budget-aware Tavily search query. Uses a price range for high budgets.
    Alternate queries on retry attempts to diversify results.
    """
    budget = state.budget
    priority = state.priority
    category = state.category

    if budget and budget >= 100000:
        floor = int(budget * 0.40)
        budget_str = f"between ₹{floor:,} and ₹{budget:,}"
    elif budget:
        budget_str = f"under ₹{budget:,}"
    else:
        budget_str = ""

    if attempt == 0:
        return f"best {category} {budget_str} for {priority} in India 2025 buy"
    elif attempt == 1:
        # Retry: more specific to actual purchase pages
        return f"top {category} {budget_str} {priority} buy India price 2025 site:amazon.in OR site:flipkart.com"
    else:
        # Second retry: broaden to value-focused query
        return f"{category} {budget_str} best value {priority} India 2026"


def _extract_candidates_from_snippets(snippets_text: str, state: AppState) -> List[str]:
    """Calls LLM to extract up to 8 real product names from search snippets."""
    def _call_groq(api_key: str):
        client = Groq(api_key=api_key)
        budget_display = f"₹{state.budget:,}" if state.budget else "N/A"
        prompt_content = (
            f"Category: {state.category}\n"
            f"User Priority: {state.priority}\n"
            f"Budget: {budget_display}\n\n"
            f"Search Snippets:\n{snippets_text}"
        )
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": IDENTIFY_PRODUCTS_PROMPT},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    try:
        raw_out = key_manager.execute_groq(_call_groq)
        cleaned = clean_json_response(raw_out)
        parsed = ensure_dict(json.loads(cleaned))
        raw_candidates = parsed.get("products", [])

        clean_candidates = []
        for name in raw_candidates:
            if (isinstance(name, str)
                    and len(name.strip()) > 3
                    and "amazon" not in name.lower()
                    and "flipkart" not in name.lower()
                    and not name.lower().startswith("best ")
                    and not name.lower().startswith("top ")):
                clean_candidates.append(name.strip())
        return clean_candidates

    except Exception as e:
        logger.error(f"LLM candidate extraction failed: {e}")
        return []


def handle_identify_products(task: SubTask, state: AppState) -> str:
    """
    Handles identify_products subtask for open-ended queries.

    Pipeline:
      1. Tavily search (budget-range query, 8 results)
      2. LLM extracts up to 8 candidate names
      3. Pricing verification pass on all candidates
      4. If <2 in-budget: RETRY with alternate search query (max 2 retries)
      5. LLM Selector Agent picks the best 3 for deep analysis
    """
    if state.target_products:
        prods_str = ", ".join(state.target_products)
        return f"Identified target products: {prods_str}"

    all_priced: Dict[str, Dict[str, Any]] = {}  # name -> pricing dict (deduplicated across retries)
    max_search_attempts = 3

    for attempt in range(max_search_attempts):
        if attempt > 0:
            within_so_far = [p for p in all_priced.values() if p.get("within_budget")]
            if len(within_so_far) >= 2:
                break  # Enough in-budget candidates already — no need to retry
            console.print(f"  [yellow]  ⟳ Retry {attempt}: fewer than 2 in-budget candidates found. Searching with alternate query...[/yellow]")

        query = _build_search_query(state, attempt)
        console.print(f"  [dim]  → Search attempt {attempt + 1}: \"{query}\"[/dim]")
        search_res = search(query=query, max_results=8)

        snippets_text = ""
        for idx, item in enumerate(search_res, 1):
            snippets_text += f"\n--- Result {idx} ---\nTitle: {item.get('title', '')}\nSnippet: {item.get('content', '')}\n"

        candidates = _extract_candidates_from_snippets(snippets_text, state)

        if attempt == 0:
            console.print(f"  [dim]  → Extracted {len(candidates)} raw candidates: {', '.join(candidates)}[/dim]")

        # Pricing pass — only for candidates not already priced in previous attempts
        new_candidates = [c for c in candidates if c not in all_priced]
        if new_candidates and attempt > 0:
            console.print(f"  [dim]  → {len(new_candidates)} new candidates to price-verify[/dim]")

        for prod_name in new_candidates:
            state.get_or_create_product(prod_name)
            pricing = run_pricing_executor(prod_name, state)
            price_inr = pricing.get("price_inr")
            
            if state.budget and isinstance(price_inr, (int, float)):
                within = price_inr <= state.budget
            else:
                within = True  # No budget set → treat all as in-budget
            
            all_priced[prod_name] = {
                "name": prod_name,
                "price_inr": price_inr,
                "formatted": pricing.get("formatted_price", "N/A"),
                "within_budget": within
            }

    # Display full pricing verification results
    priced_list = list(all_priced.values())
    within_budget = [p for p in priced_list if p["within_budget"]]
    over_budget = [p for p in priced_list if not p["within_budget"]]

    console.print(f"  [dim]  → Pricing verified: {len(priced_list)} total | {len(within_budget)} within budget | {len(over_budget)} over budget[/dim]")
    for p in sorted(priced_list, key=lambda x: x.get("price_inr") or 0, reverse=True):
        status = "[green]✔ within[/green]" if p["within_budget"] else "[red]✘ over[/red]"
        console.print(f"    {status}  {p['name']} — {p['formatted']}")

    if not within_budget and not priced_list:
        logger.error(f"No candidates found for query: '{state.user_prompt}'")
        return "Product identification could not resolve specific models. Please refine your query with specific product names."

    # ─── LLM Selector Agent ────────────────────────────────────────────────────
    console.print(f"  [dim]  → Running Selector Agent to pick best 3...[/dim]")
    final_names = run_selector(
        priced_candidates=priced_list,
        budget=state.budget,
        priority=state.priority,
        category=state.category,
        user_prompt=state.user_prompt
    )

    if not final_names:
        # Hard fallback — take top within-budget by price descending
        final_names = [p["name"] for p in sorted(within_budget, key=lambda x: x.get("price_inr") or 0, reverse=True)[:3]]

    # Supplement with closest over-budget if fewer than 2 selected
    if len(final_names) < 2:
        sorted_over = sorted(
            [p for p in over_budget if isinstance(p.get("price_inr"), (int, float))],
            key=lambda x: x["price_inr"]
        )
        needed = 2 - len(final_names)
        extra = [p["name"] for p in sorted_over[:needed]]
        final_names += extra
        if extra:
            console.print(f"  [yellow]  ⚠ Fewer than 2 in-budget candidates. Added {len(extra)} closest over-budget option(s).[/yellow]")

    # Update state with selector's choices
    state.target_products = final_names
    for name in final_names:
        state.get_or_create_product(name)

    console.print(f"  [bold green]  → Selector picked ({len(final_names)}): {', '.join(final_names)}[/bold green]")
    return f"Identified candidate products: {', '.join(final_names)}"


def run_orchestrator(state: AppState, verbose: bool = True) -> AppState:
    """
    Topological orchestrator that executes planned subtasks in dependency order.
    Loops through ready steps (is_step_ready == True), dispatches them to specialized
    executors, updates AppState, and tracks progress.

    NOTE: For open-ended queries, `handle_identify_products` runs pricing on all
    candidates, retries if needed, then uses the LLM Selector Agent to pick the
    best 3. The subsequent `collect_pricing` step uses cached pricing data.
    """
    if verbose:
        console.print(Panel.fit(
            f"[bold cyan]Orchestrator Executing Plan ({len(state.plan)} Subtasks)[/bold cyan]\n"
            f"Prompt: \"{state.user_prompt}\"\n"
            f"Category: {state.category} | Priority: {state.priority} | Budget: {state.budget or 'N/A'}"
        ))

    max_loops = len(state.plan) * 3
    loop_count = 0

    while loop_count < max_loops:
        loop_count += 1
        ready_tasks = state.get_ready_steps()

        # Filter out generate_recommendation step (handled in Phase 3 by Assembler)
        executable_tasks = [t for t in ready_tasks if t.step_type != "generate_recommendation"]

        if not executable_tasks:
            pending_executables = [
                t for t in state.plan
                if t.step_type != "generate_recommendation" and t.status != "completed"
            ]
            if not pending_executables:
                if verbose:
                    console.print("[bold green]✔ All executor subtasks completed successfully![/bold green]")
                break
            else:
                logger.warning(f"No executable ready tasks found, but {len(pending_executables)} remain pending. Breaking loop.")
                break

        for task in executable_tasks:
            task.status = "in_progress"
            step_type = task.step_type
            result_summary = ""

            try:
                if step_type == "identify_products":
                    result_summary = handle_identify_products(task, state)

                elif step_type == "collect_specs":
                    products = resolve_target_product_names(task, state)
                    specs_outs = []
                    for prod_name in products:
                        res = run_specs_executor(prod_name, state)
                        specs_outs.append(f"{prod_name}: CPU={res.get('processor', res.get('processor_chipset', 'N/A'))}, GPU={res.get('gpu', 'N/A')}")
                    result_summary = " | ".join(specs_outs)

                elif step_type == "collect_pricing":
                    products = resolve_target_product_names(task, state)
                    pricing_outs = []
                    for prod_name in products:
                        # Skip if pricing already collected during budget verification pass
                        prod_state = state.get_or_create_product(prod_name)
                        if prod_state.pricing and "price_inr" in prod_state.pricing:
                            pricing_outs.append(f"{prod_name}: Price={prod_state.pricing.get('formatted_price', 'N/A')} (cached)")
                        else:
                            res = run_pricing_executor(prod_name, state)
                            pricing_outs.append(f"{prod_name}: Price={res.get('formatted_price', 'N/A')}")
                    result_summary = " | ".join(pricing_outs)

                elif step_type == "analyze_performance":
                    products = resolve_target_product_names(task, state)
                    perf_outs = []
                    for prod_name in products:
                        res = run_performance_executor(prod_name, state)
                        perf_outs.append(f"{prod_name}: Score={res.get('qualitative_score_100', 'N/A')}/100")
                    result_summary = " | ".join(perf_outs)

                else:
                    result_summary = f"Unknown step type: {step_type}"

                # Mark step completed in AppState
                state.mark_step_completed(task.id, result=result_summary)

                if verbose:
                    console.print(
                        f"  [bold green][✔] Step {task.id}[/bold green] "
                        f"([cyan]{task.step_type}[/cyan] - {task.target_product or 'All'}): {result_summary}"
                    )

            except Exception as e:
                logger.error(f"Error executing step {task.id} ({task.step_type}): {e}")
                task.status = "failed"
                task.result = f"Error: {str(e)}"

    return state
