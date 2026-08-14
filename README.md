# Product Comparison Agent — Plan-and-Execute Multi-Agent System

An autonomous, stateful multi-agent system designed for in-depth product comparisons (Laptops & Smartphones). Built upon the **Plan-and-Execute** paradigm, this system decomposes natural language user queries into dependency-aware execution graphs, grounds hardware specifications via live web search and LLM-assisted tools, and synthesizes priority-weighted purchasing recommendations.

---

## 📚 Theoretical Foundation

This project is conceptually rooted in the groundbreaking paper by Wang et al. (2023):  
> **"Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models"**  
> *Lei Wang, Wanyu Xu, Yihuai Lan, Zhiqiang Hu, Yunshi Lan, Roy Ka-Wei Lee, Ee-Peng Lim* (arXiv:[2305.04091](https://arxiv.org/abs/2305.04091))

### How This Project Extends Paper 2305.04091:
While paper 2305.04091 introduces zero-shot prompt decomposition to reduce reasoning and step-skipping errors, our system extends this framework into a **Production Multi-Agent Architecture**:
1. **Explicit Graph Decomposition**: Instead of a single LLM generating prose reasoning, our **Planner Agent** (`llama-3.3-70b-versatile`) outputs a structured JSON subtask DAG with explicit `depends_on` step IDs.
2. **Stateful Dependency Resolution**: Downstream agents (e.g., Performance Executor) explicitly consume typed outputs produced by upstream agents (e.g., Specs Executor) via a shared Pydantic `AppState`.
3. **Grounded Tool Layer**: Hallucination risks regarding hardware SKU rankings are eliminated by grounding specs via Tavily search and an **LLM-powered benchmark lookup tool** (`spec_lookup.py`), avoiding reliance on parametric memory.

---

## 🏗️ System Architecture & Workflow

```
[ User Request ]
       │
       ▼
┌──────────────┐
│ Planner LLM  │ ──► Generates JSON Subtask Plan (depends_on DAG)
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│               Topological Orchestrator                 │
│  (Executes ready tasks sequentially in dependency order)│
└──────┬────────────────────┬────────────────────┬───────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│    Specs     │     │   Pricing    │     │   Performance    │
│   Executor   │     │   Executor   │     │     Executor     │
│ (Tavily Search)    │ (India INR)  │     │(Reuses State     │
│ (8B-Instant) │     │ (8B-Instant) │     │ + LLM Spec Lookup│
└──────┬───────┘     └──────┬───────┘     │ 70B-Versatile)   │
       │                    │             └────────┬─────────┘
       └────────────────────┼──────────────────────┘
                            │ (Updates Pydantic AppState)
                            ▼
                  ┌──────────────────┐
                  │  Assembler LLM   │
                  │ (70B-Versatile)  │
                  └─────────┬────────┘
                            │ (Synthesizes Priority-Weighted Report)
                            ▼
               [ Final Recommendation Report ]
```

---

## 🚀 Key Technical Innovations

1. **Multi-Key Failover Pool (`key_manager.py`)**:
   - Manages pools of Groq (`GROQ_API_KEY1..3`) and Tavily (`TAVILY_API_KEY1..3`) API keys loaded from `.env`.
   - Automatically catches HTTP 429 / Rate Limit / Quota Exceeded exceptions and cycles to the next key seamlessly without crashing executions.

2. **Zero Keyword Matching — LLM-Assisted Hardware Lookup (`spec_lookup.py`)**:
   - Completely avoids fragile string/regex/keyword matching (e.g., matching `"RTX 4060"` in raw web text).
   - Uses `llama-3.1-8b-instant` as an LLM tool call to analyze raw component descriptions and map them to standardized benchmark tier metrics (Tiers 1–4, 1–100 scores, VRAM, and performance verdicts).

3. **Strict Non-Redundant Execution**:
   - The Performance Executor relies **only** on specs already collected in `AppState.products[name].specs` by upstream steps.
   - It explicitly avoids re-querying search engines for raw specs, proving clean information passing across subtask dependencies.

4. **Structured JSON Run Logging (`logger_util.py`)**:
   - Every run automatically dumps a complete execution trace to `backend/logs/{timestamp}.json` containing the original prompt, plan, extracted products data, recommendation text, and total latency in seconds.

---

## 🛠️ Tech Stack & Model Mapping

| Role / Component | Model / Tool | Why Selected |
| :--- | :--- | :--- |
| **Planner Agent** | `llama-3.3-70b-versatile` (Groq) | High reasoning capacity for intent parsing & DAG subtask generation |
| **Specs Executor** | `llama-3.1-8b-instant` (Groq) | Ultra-fast structured extraction from web snippets |
| **Pricing Executor** | `llama-3.1-8b-instant` (Groq) | Fast currency & budget status parsing |
| **Hardware Lookup Tool** | `llama-3.1-8b-instant` (Groq) | LLM hardware evaluation without string keyword matching |
| **Performance Executor** | `llama-3.3-70b-versatile` (Groq) | Deep qualitative reasoning over pre-collected hardware specs |
| **Assembler Agent** | `llama-3.3-70b-versatile` (Groq) | Priority-weighted final synthesis and decision matrix generation |
| **Web Search Tool** | Tavily Python SDK (`tavily-python`) | Structured web search snippets (`title`, `content`, `url`, `score`) |
| **Backend & State** | FastAPI + Pydantic v2 | Async-ready REST API with strictly typed schema validation |
| **Console & UI** | Rich (`rich`) | Step-by-step terminal progress bars and markdown rendering |

---

## 📁 Repository Structure

```
CAT-1/
├── backend/
│   ├── main.py                # FastAPI app + CLI entry point
│   ├── planner.py             # Subtask JSON plan generator (llama-3.3-70b)
│   ├── orchestrator.py        # Topological dependency-ordered execution loop
│   ├── assembler.py           # Final recommendation synthesis agent
│   ├── state.py               # AppState, ProductState & SubTask Pydantic schemas
│   ├── logger_util.py         # Structured JSON run log persistence
│   ├── executors/
│   │   ├── specs.py           # Specs extraction executor (llama-3.1-8b)
│   │   ├── pricing.py         # Pricing extraction executor (llama-3.1-8b)
│   │   └── performance.py     # Performance evaluation executor (llama-3.3-70b)
│   ├── tools/
│   │   ├── key_manager.py     # API key rotation & 429 rate limit failover
│   │   ├── web_search.py      # Tavily search tool wrapper
│   │   └── spec_lookup.py     # LLM-powered hardware benchmark tool
│   └── logs/                  # Persistent JSON run logs
├── tests/
│   ├── test_state_planner.py  # Pytest suite for state & dependency resolution
│   ├── test_groq_smoke.py      # Standalone Groq API smoke test script
│   ├── test_tavily_smoke.py    # Standalone Tavily API smoke test script
│   ├── test_planner.py         # Standalone planner module test script
│   ├── test_tools.py           # Standalone tool layer test script
│   ├── test_executors.py       # Standalone executors integration test script
│   ├── test_orchestrator.py    # Orchestrator dependency loop test script
│   ├── test_end_to_end.py      # Full end-to-end pipeline integration script
│   └── run_phase9_evaluation.py# 4-prompt evaluation benchmark suite
├── requirements.txt           # Dependency requirements
├── checklist.md               # Build phase checklist & milestone tracker
└── DEMO_GUIDE.md              # 4-5 minute live presentation guide
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites & Installation
Ensure Python 3.10+ is installed:

```bash
# Navigate to CAT-1 folder
cd CAT-1

# Activate your virtual environment
source ../.venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. API Credentials Setup
Ensure `.env` in your workspace root contains your Groq and Tavily API keys:

```env
GROQ_API_KEY1=gsk_...
GROQ_API_KEY2=gsk_...
GROQ_API_KEY3=gsk_...
TAVILY_API_KEY1=tvly-...
TAVILY_API_KEY2=tvly-...
TAVILY_API_KEY3=tvly-...
```

### 3. Run via Interactive Console Chat
Run the agent in interactive chat mode directly from the command line:

```bash
python backend/main.py
```

The agent will display a welcome prompt and wait for your input:
```
🤖 Welcome to Agentic AI Lab
Ask any product comparison query (Laptops & Smartphones).
Type 'exit' or 'quit' to exit.

User > Compare Lenovo Legion 5 and ASUS TUF Gaming F15 for AI development under ₹90,000.
```

*(Note: You can also pass a single prompt directly via flag: `python backend/main.py --prompt "..."`)*

### 4. Run via FastAPI Web Server
Start the uvicorn API server:

```bash
uvicorn backend.main:app --reload --port 8000
```

- Health check: `GET http://localhost:8000/`
- Compare API: `POST http://localhost:8000/compare`
  ```json
  {
    "prompt": "Compare iPhone 15, Samsung Galaxy S24, and OnePlus 12 for photography."
  }
  ```

---

## 🧪 Testing & Evaluation

### Run Unit Tests (`pytest`)
```bash
pytest tests/test_state_planner.py
```

### Run Benchmark Evaluation Suite (Phase 9)
Executes all 4 required evaluation queries and verifies dynamic planning, spec reuse, and log persistence:

```bash
python tests/run_phase9_evaluation.py
```

---

## ⚠️ Documented Limitations & Future Work

1. **Sequential Step Execution**: Subtasks are executed sequentially in topological order. *Future Work: Add async task dispatching for parallel step execution.*
2. **Fixed Category Scope**: Scope is currently locked to Laptops and Smartphones. *Future Work: Support GPUs, headphones, and desktop components.*
3. **No Dynamic Replanning Loop**: If a tool call fails, the executor returns a baseline fallback rather than triggering a planner replan loop. *Future Work: Implement reflection & replanning agent loops.*
