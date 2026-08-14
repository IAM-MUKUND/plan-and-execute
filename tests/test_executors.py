import sys
import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add CAT-1 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.state import AppState
from backend.executors.specs import run_specs_executor
from backend.executors.pricing import run_pricing_executor
from backend.executors.performance import run_performance_executor

console = Console()

def test_single_product_executors():
    console.print(Panel.fit("[bold cyan]Executors Standalone Test Suite (Phase 4)[/bold cyan]"))
    
    state = AppState(
        user_prompt="Compare Lenovo Legion 5 for AI development under ₹90,000",
        category="laptop",
        priority="ML",
        budget=90000,
        target_products=["Lenovo Legion 5"]
    )
    
    product_name = "Lenovo Legion 5"
    
    # 1. Run Specs Executor (llama-3.1-8b-instant + Tavily)
    console.print(f"\n[bold yellow]1. Running Specs Executor for:[/bold yellow] {product_name}")
    specs_res = run_specs_executor(product_name, state)
    console.print(f"[bold green]✔ Specs Collected:[/bold green]")
    console.print(f"   CPU : {specs_res.get('processor')}")
    console.print(f"   GPU : {specs_res.get('gpu')}")
    console.print(f"   RAM : {specs_res.get('ram')}")
    console.print(f"   OS  : {specs_res.get('os')}")

    # 2. Run Pricing Executor (llama-3.1-8b-instant + Tavily)
    console.print(f"\n[bold yellow]2. Running Pricing Executor for:[/bold yellow] {product_name}")
    pricing_res = run_pricing_executor(product_name, state)
    console.print(f"[bold green]✔ Pricing Collected:[/bold green]")
    console.print(f"   Price (INR)   : {pricing_res.get('formatted_price')}")
    console.print(f"   Within Budget : {pricing_res.get('within_budget')} (Budget: ₹{state.budget})")

    # 3. Run Performance Executor (llama-3.3-70b-versatile + Spec Lookup Tool + Stored Specs)
    console.print(f"\n[bold yellow]3. Running Performance Executor for:[/bold yellow] {product_name}")
    perf_res = run_performance_executor(product_name, state)
    console.print(f"[bold green]✔ Performance Evaluated:[/bold green]")
    console.print(f"   Qualitative Score : {perf_res.get('qualitative_score_100')}/100")
    console.print(f"   Priority Verdict  : {perf_res.get('priority_verdict')}")
    console.print(f"   Specs Reused Flag : {perf_res.get('specs_reused_from_state')}")

    # Verify AppState state updates
    stored_prod = state.products.get("lenovo legion 5")
    assert stored_prod is not None
    assert stored_prod.specs is not None
    assert stored_prod.pricing is not None
    assert stored_prod.performance is not None
    
    console.print(Panel.fit("[bold green]✔ All 3 Executors completed successfully and updated AppState![/bold green]"))

if __name__ == "__main__":
    test_single_product_executors()
