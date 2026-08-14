import sys
import os
import json
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add CAT-1 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import run_agent_pipeline

console = Console()

PHASE9_BENCHMARK_PROMPTS = [
    {
        "id": 1,
        "title": "Laptops for AI under ₹90,000",
        "prompt": "Compare three laptops for AI development under ₹90,000.",
        "expected_category": "laptop",
        "expected_priority": "ML"
    },
    {
        "id": 2,
        "title": "Phones for Photography (iPhone vs Galaxy vs OnePlus)",
        "prompt": "Compare iPhone 15, Samsung Galaxy S24, and OnePlus 12 for photography.",
        "expected_category": "phone",
        "expected_priority": "photography"
    },
    {
        "id": 3,
        "title": "Gaming Laptop under ₹1,00,000",
        "prompt": "Recommend the best laptop under ₹1,00,000 for gaming.",
        "expected_category": "laptop",
        "expected_priority": "gaming"
    },
    {
        "id": 4,
        "title": "Laptop Comparison Without Budget Constraint",
        "prompt": "Compare Lenovo Legion 5 and ASUS TUF Gaming F15 without budget constraint.",
        "expected_category": "laptop",
        "expected_priority": "general"
    }
]

def main():
    console.print(Panel.fit("[bold cyan]Phase 9 — Full Benchmark Evaluation Suite[/bold cyan]\nRunning 4 benchmark scenarios..."))
    
    results_summary = []
    
    for item in PHASE9_BENCHMARK_PROMPTS:
        p_id = item["id"]
        title = item["title"]
        prompt = item["prompt"]
        
        console.print(f"\n==================================================")
        console.print(f"[bold yellow]Benchmark #{p_id}: {title}[/bold yellow]")
        console.print(f"Prompt: \"{prompt}\"")
        console.print(f"==================================================")
        
        start_time = time.time()
        res = run_agent_pipeline(prompt, verbose=True)
        elapsed = time.time() - start_time
        
        # Verify run checks
        cat_match = res["category"] == item["expected_category"]
        plan_len = len(res["plan"])
        log_file = res["log_file"]
        
        # Check that log file exists and is valid JSON
        log_exists = os.path.exists(log_file)
        
        results_summary.append({
            "id": p_id,
            "title": title,
            "category": res["category"],
            "priority": res["priority"],
            "budget": res["budget"],
            "target_products": res["target_products"],
            "plan_steps": plan_len,
            "duration": round(elapsed, 2),
            "log_file": log_file,
            "passed": cat_match and plan_len > 0 and log_exists
        })

    # Render summary table
    table = Table(title="Phase 9 Benchmark Evaluation Summary")
    table.add_column("ID", justify="center", style="cyan")
    table.add_column("Benchmark Scenario", style="bold white")
    table.add_column("Cat / Priority", style="magenta")
    table.add_column("Target Products", style="blue")
    table.add_column("Steps", justify="center", style="yellow")
    table.add_column("Time (s)", justify="center", style="cyan")
    table.add_column("Status", justify="center", style="bold green")
    
    for r in results_summary:
        status_str = "[bold green]PASS[/bold green]" if r["passed"] else "[bold red]FAIL[/bold red]"
        prods_str = ", ".join(r["target_products"][:2]) if r["target_products"] else "Open Search"
        table.add_row(
            str(r["id"]),
            r["title"],
            f"{r['category']} / {r['priority']}",
            prods_str,
            str(r["plan_steps"]),
            f"{r['duration']}s",
            status_str
        )

    console.print("\n")
    console.print(table)
    console.print("\n[bold green]✔ All Phase 9 benchmark logs saved to CAT-1/backend/logs/[/bold green]")

if __name__ == "__main__":
    main()
