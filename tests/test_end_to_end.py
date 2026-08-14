import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Add CAT-1 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.planner import generate_plan
from backend.orchestrator import run_orchestrator
from backend.assembler import assemble_final_recommendation

console = Console()

def run_end_to_end(user_prompt: str):
    console.print(Panel.fit(f"[bold magenta]End-to-End Execution[/bold magenta]\nPrompt: \"{user_prompt}\""))
    
    # 1. Planner Phase
    console.print("\n[bold yellow]Phase 2: Generating Plan...[/bold yellow]")
    state = generate_plan(user_prompt)
    
    # 2. Orchestrator Phase (Executors & Tools)
    console.print("\n[bold yellow]Phase 5: Running Orchestrator...[/bold yellow]")
    executed_state = run_orchestrator(state, verbose=True)
    
    # 3. Assembler Phase (Synthesis)
    console.print("\n[bold yellow]Phase 6: Assembling Final Recommendation...[/bold yellow]")
    final_report = assemble_final_recommendation(executed_state)
    
    console.print(Panel.fit("[bold green]Final Output Report:[/bold green]"))
    console.print(Markdown(final_report))
    
    return final_report

def main():
    prompt = "Compare Lenovo Legion 5 and ASUS TUF Gaming F15 for AI development under ₹90,000."
    run_end_to_end(prompt)

if __name__ == "__main__":
    main()
