import time
import argparse
import sys
import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Add CAT-1 to sys.path so imports work properly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.planner import generate_plan
from backend.orchestrator import run_orchestrator
from backend.assembler import assemble_final_recommendation
from backend.logger_util import save_execution_log

app = FastAPI(
    title="Product Comparison Agent API",
    description="Plan-and-Execute Agent for Laptop & Phone Comparisons",
    version="1.0.0"
)

console = Console()

class CompareRequest(BaseModel):
    prompt: str = Field(..., json_schema_extra={"example": "Compare Lenovo Legion 5 and ASUS TUF Gaming F15 for AI development under ₹90,000."})

class CompareResponse(BaseModel):
    user_prompt: str
    category: str
    priority: str
    budget: Optional[int] = None
    target_products: List[str]
    plan: List[Dict[str, Any]]
    products: Dict[str, Any]
    final_recommendation: str
    execution_time_seconds: float
    log_file: str

def run_agent_pipeline(user_prompt: str, verbose: bool = True) -> Dict[str, Any]:
    """Runs full Planner -> Orchestrator -> Assembler -> Logger pipeline."""
    start_time = time.time()
    
    if verbose:
        console.print(Panel.fit(f"[bold magenta]Product Comparison Agent[/bold magenta]\nPrompt: \"{user_prompt}\""))
    
    # Phase 1: Planner
    if verbose:
        console.print("\n[bold yellow]Phase 1: Generating Dynamic Plan...[/bold yellow]")
    state = generate_plan(user_prompt)

    if verbose:
        plan_summary = ", ".join(
            f"Step {t.id} ({t.step_type}{'→' + t.target_product if t.target_product else ''})"
            for t in state.plan
        )
        console.print(f"  [dim]Plan: {plan_summary}[/dim]")

    # Phase 2: Orchestrator
    if verbose:
        console.print("\n[bold yellow]Phase 2: Executing Orchestrator (Topological Dispatch)...[/bold yellow]")
    executed_state = run_orchestrator(state, verbose=verbose)

    # Phase 3: Assembler
    if verbose:
        console.print("\n[bold yellow]Phase 3: Assembling Final Recommendation...[/bold yellow]")
    final_report = assemble_final_recommendation(executed_state)

    duration = time.time() - start_time

    # Phase 4: Logger
    if verbose:
        console.print("\n[bold yellow]Phase 4: Saving Execution Log...[/bold yellow]")
    log_file = save_execution_log(executed_state, final_report, duration)
    
    if verbose:
        console.print(Panel.fit("[bold green]Final Recommendation Report:[/bold green]"))
        console.print(Markdown(final_report))
        console.print(f"\n[bold green]✔ Run Log Saved:[/bold green] {log_file} (Duration: {duration:.2f}s)")

    products_out = {}
    for key, pstate in executed_state.products.items():
        products_out[pstate.name] = {
            "specs": pstate.specs,
            "pricing": pstate.pricing,
            "performance": pstate.performance
        }

    return {
        "user_prompt": executed_state.user_prompt,
        "category": executed_state.category,
        "priority": executed_state.priority,
        "budget": executed_state.budget,
        "target_products": executed_state.target_products,
        "plan": [t.model_dump() for t in executed_state.plan],
        "products": products_out,
        "final_recommendation": final_report,
        "execution_time_seconds": round(duration, 2),
        "log_file": log_file
    }

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Product Comparison Agent API",
        "endpoints": {
            "health": "GET /",
            "compare": "POST /compare"
        }
    }

@app.post("/compare", response_model=CompareResponse)
def compare_endpoint(req: CompareRequest):
    if not req.prompt or len(req.prompt.strip()) < 5:
        raise HTTPException(status_code=400, detail="Prompt must be at least 5 characters long.")
    result = run_agent_pipeline(req.prompt, verbose=False)
    return CompareResponse(**result)

def interactive_chat_loop():
    """Interactive CLI chat interface waiting for user input."""
    console.print(Panel.fit(
        "[bold cyan]Product Comparison Agent — Interactive Console Chat[/bold cyan]\n"
        "Ask any product comparison query (Laptops & Smartphones).\n"
        "Type [bold yellow]'exit'[/bold yellow] or [bold yellow]'quit'[/bold yellow] to exit.",
        title="🤖 Welcome to Agentic AI Lab"
    ))
    
    while True:
        try:
            user_input = console.input("\n[bold green]User > [/bold green]").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n[bold cyan]Goodbye! Shutting down Product Comparison Agent.[/bold cyan]")
                break
            
            run_agent_pipeline(user_input, verbose=True)
        except (KeyboardInterrupt, EOFError):
            console.print("\n\n[bold cyan]Goodbye! Exiting agent chat.[/bold cyan]")
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Product Comparison Agent CLI")
    parser.add_argument("--prompt", type=str, help="Single prompt execution mode", default=None)
    args = parser.parse_args()

    if args.prompt:
        run_agent_pipeline(args.prompt, verbose=True)
    else:
        interactive_chat_loop()
