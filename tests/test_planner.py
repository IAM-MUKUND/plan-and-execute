import sys
import os
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add CAT-1 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.planner import generate_plan

console = Console()

TEST_PROMPTS = [
    "Compare Lenovo Legion 5 and ASUS TUF Gaming F15 for AI development under ₹90,000.",
    "Compare iPhone 15, Samsung Galaxy S24, and OnePlus 12 for photography.",
    "Recommend the best laptop under ₹1,00,000 for gaming."
]

def main():
    console.print(Panel.fit("[bold cyan]Planner Module Test Suite (Phase 2)[/bold cyan]\nExecuting planner on 3 distinct prompts..."))
    
    saved_plans = []
    
    for idx, prompt in enumerate(TEST_PROMPTS, 1):
        console.print(f"\n[bold yellow]Prompt #{idx}:[/bold yellow] \"{prompt}\"")
        
        state = generate_plan(prompt)
        
        console.print(f"  Category       : [green]{state.category}[/green]")
        console.print(f"  Priority       : [magenta]{state.priority}[/magenta]")
        console.print(f"  Budget         : [cyan]{state.budget}[/cyan]")
        console.print(f"  Target Products: [blue]{state.target_products}[/blue]")
        
        table = Table(title=f"Generated Subtask Plan ({len(state.plan)} steps)")
        table.add_column("Step ID", justify="center", style="cyan")
        table.add_column("Step Type", style="bold green")
        table.add_column("Target Product", style="blue")
        table.add_column("Description", style="white")
        table.add_column("Depends On", justify="center", style="yellow")
        
        for task in state.plan:
            table.add_row(
                str(task.id),
                task.step_type,
                task.target_product or "-",
                task.description,
                str(task.depends_on)
            )
            
        console.print(table)
        saved_plans.append(json.loads(state.dump_json()))

    # Save to logs/test_plans.json
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    out_file = os.path.join(logs_dir, "test_plans.json")
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(saved_plans, f, indent=2)
        
    console.print(f"\n[bold green]✔ Saved generated plan evidence to:[/bold green] {out_file}")

if __name__ == "__main__":
    main()
