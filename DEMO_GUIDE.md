# 4-5 Minute Live Demo Guide & Presentation Script

This guide outlines the recommended live presentation script and execution steps for demonstrating the **Product Comparison Agent**.

---

## ⏱️ Presentation Outline (4:30 Total)

```
0:00 ── 0:30 ──► 1. Problem Introduction & Theoretical Origin (arXiv:2305.04091)
0:30 ── 1:15 ──► 2. Architecture Overview & Technical Innovations
1:15 ── 2:45 ──► 3. Live Demo: Planner & Orchestrator Execution
2:45 ── 3:45 ──► 4. Live Demo: Assembler Report & Verification Proof
3:45 ── 4:30 ──► 5. Summary of Benchmark Logs & Limitations
```

---

## 🎙️ Step-by-Step Script & Demo Actions

### 1. Problem Introduction & Theory (0:00 – 0:30)
- **Talk Track**:
  > *"Single-shot LLM prompts often hallucinate hardware specifications or skip intermediate steps when evaluating products. To solve this, our system implements a **Plan-and-Execute Multi-Agent Architecture**, conceptually originating from Wang et al. 2023 (Plan-and-Solve Prompting, arXiv:2305.04091). We decompose complex natural language comparison queries into explicit subtask execution graphs."*

### 2. Architecture Overview (0:30 – 1:15)
- **Talk Track**:
  > *"Our system features 4 key innovations:*
  > 1. **Model Tiering**: Using `llama-3.3-70b-versatile` for high-level planning and final synthesis, and fast `llama-3.1-8b-instant` for structured extraction.
  > 2. **KeyManager Rotation**: 3 API keys per provider to handle rate limits automatically.
  > 3. **Zero Keyword Matching**: An LLM-assisted hardware benchmark tool (`spec_lookup.py`) evaluates raw GPU/CPU specs into standard tiers without string/keyword matching.
  > 4. **Strict State Passing**: Performance Executor reuses pre-collected specs from Pydantic `AppState` without re-querying search tools."*

### 3. Live Execution Demo (1:15 – 2:45)
- **Demo Action**: Run the interactive agent chat interface in your terminal:
  ```bash
  python backend/main.py
  ```
  The agent will display a welcome banner and wait for your prompt:
  ```
  🤖 Welcome to Agentic AI Lab
  Ask any product comparison query (Laptops & Smartphones).
  
  User > Compare Lenovo Legion 5 and ASUS TUF Gaming F15 for AI development under ₹90,000.
  ```
- **Talk Track while terminal updates**:
  - Point to the **Planner phase**: Show the generated JSON subtasks and their `depends_on` step IDs.
  - Point to the **Orchestrator phase**: Show step-by-step progress logging (`[✔] Step 2: Specs collected`, `[✔] Step 4: Pricing collected`).
  - Highlight that **Step 6 (Performance)** reused specs collected in Step 2 directly from state.

### 4. Final Assembler Report & Verification (2:45 – 3:45)
- **Talk Track**:
  - Show the final Markdown report rendered on screen.
  - Point out why **ASUS TUF Gaming F15** won:
    - Superior RTX 4060 GPU (8GB VRAM vs 6GB VRAM on Legion 5's RTX 2060) for PyTorch/CUDA workloads.
    - Fits within the ₹90,000 budget at **₹84,990**, whereas Legion 5 costs **₹1,25,000** (exceeds budget).

### 5. Log Evidence & Wrap-Up (3:45 – 4:30)
- **Demo Action**: Open the generated run log:
  ```bash
  cat backend/logs/2026*.json | head -n 30
  ```
- **Talk Track**:
  > *"Every run automatically dumps a persistent JSON log in `backend/logs/` with complete step execution traces, verification flags, and timing metrics. Thank you!"*
