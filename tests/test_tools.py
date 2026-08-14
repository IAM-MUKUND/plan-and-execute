import sys
import os
import json
from rich.console import Console
from rich.panel import Panel

# Add CAT-1 to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.tools.web_search import search
from backend.tools.spec_lookup import lookup_spec_tier

console = Console()

def main():
    console.print(Panel.fit("[bold cyan]Tool Layer Test Suite (Phase 3)[/bold cyan]"))
    
    # 1. Test Tavily Search
    query = "Lenovo Legion 5 AMD Ryzen 7 7840HS RTX 4060 specs"
    console.print(f"\n[bold yellow]1. Testing Tavily Web Search:[/bold yellow] Query = '{query}'")
    search_results = search(query=query, max_results=2)
    
    if search_results:
        console.print(f"[bold green]✔ Retrieved {len(search_results)} search results successfully.[/bold green]")
        console.print(f"   Top Result Title: {search_results[0]['title']}")
        console.print(f"   URL             : {search_results[0]['url']}")
    else:
        console.print("[bold red]✘ Tavily Search returned empty results.[/bold red]")

    # 2. Test LLM-Powered Spec Lookup Tool (No keyword matching!)
    noisy_gpu_text = "NVIDIA® GeForce RTX™ 4060 Laptop GPU 8GB GDDR6 (140W TGP, Dynamic Boost)"
    console.print(f"\n[bold yellow]2. Testing LLM-Powered Spec Lookup Tool:[/bold yellow] Input = '{noisy_gpu_text}'")
    
    lookup_res = lookup_spec_tier(category="laptop", raw_hardware_text=noisy_gpu_text)
    
    console.print(f"[bold green]✔ LLM Tool Result:[/bold green]")
    console.print(f"   Identified Model : {lookup_res.get('identified_model')}")
    console.print(f"   Tier Level       : Tier {lookup_res.get('tier_level')}")
    console.print(f"   Score (1-100)    : {lookup_res.get('performance_score_100')}")
    console.print(f"   Key Features     : {lookup_res.get('key_features')}")
    console.print(f"   Verdict          : {lookup_res.get('benchmark_summary')}")

if __name__ == "__main__":
    main()
