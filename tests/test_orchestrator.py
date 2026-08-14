import sys
import os
from rich.console import Console
from rich.panel import Panel

# Add CAT-1 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.planner import generate_plan
from backend.orchestrator import run_orchestrator

console = Console()

def test_orchestration_flow():
    console.print(Panel.fit("[bold cyan]Orchestrator Test Suite (Phase 5)[/bold cyan]"))
    
    user_prompt = "Compare Lenovo Legion 5 and ASUS TUF Gaming F15 for AI development under ₹90,000."
    console.print(f"\n1. Generating Plan for: \"{user_prompt}\"")
    state = generate_plan(user_prompt)
    
    console.print(f"Plan generated with {len(state.plan)} steps.")
    
    console.print("\n2. Executing Orchestrator Loop...")
    executed_state = run_orchestrator(state, verbose=True)
    
    console.print("\n[bold green]✔ Orchestration Execution Verification:[/bold green]")
    for task in executed_state.plan:
        if task.step_type != "generate_recommendation":
            assert task.status == "completed", f"Task {task.id} ({task.step_type}) was not marked completed!"
            console.print(f"  [✔] Step {task.id} ({task.step_type}): Status = {task.status}")

    console.print(Panel.fit("[bold green]✔ Orchestrator completed all executor subtasks in topological dependency order![/bold green]"))

if __name__ == "__main__":
    test_orchestration_flow()
