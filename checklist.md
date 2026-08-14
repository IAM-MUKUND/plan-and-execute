
# Product Comparison Agent — Build Checklist

### Plan-and-Execute Architecture (Trimmed Scope)

**Scope locked in:** Laptops + Phones only · 3 executors (Specs, Pricing, Performance) · Sequential execution · Plain console/simple UI output · JSON logging per run.

**Reference:** [arxiv.org/abs/2305.04091](https://arxiv.org/abs/2305.04091)

---

## Tech Stack (Locked In)

**LLM Inference — Groq API**

| Role                 | Model                       | Why                                                             |
| -------------------- | --------------------------- | --------------------------------------------------------------- |
| Planner              | `llama-3.3-70b-versatile` | decomposition/judgment-heavy                                    |
| Assembler            | `openai/gpt-oss-120b`     | final synthesis, most judgment-heavy step                       |
| Specs executor       | `llama-3.1-8b-instant`    | extraction/formatting, fast & cheap                             |
| Pricing executor     | `llama-3.1-8b-instant`    | extraction/formatting, fast & cheap                             |
| Performance executor | `llama-3.3-70b-versatile` | must reason over*retrieved* specs, not memorized SKU rankings |

- Call Groq directly via the `groq` SDK — no LiteLLM/provider abstraction layer, not worth it for a scoped course project.
- Groq's low latency is a deliberate choice for Phase 11 (live demo feels "alive" with sub-second executor turnaround).

**Web Search — Tavily**

- `tavily-python` SDK
- Returns structured JSON (`title`, `content`, `url`, `score`) — matches the `search(query) -> structured_result` tool spec in Phase 3 with no extra parsing layer.
- For the Performance executor specifically: don't trust any model's memorized "GPU X beats GPU Y" ranking. Either (a) have it search for a benchmark comparison when specs alone are ambiguous, or (b) hardcode a small reference/tier table as a `spec_lookup` tool for your fixed demo product set. Either counts as a legitimate tool call, not cheating — and removes hallucination risk for the specific SKUs in your demo.

**Backend — Python + FastAPI**

- FastAPI (not Flask) — async-ready, and its Pydantic integration is close to free once you're using Pydantic for state anyway.
- **Pydantic models for shared state**, not a raw dict — catches malformed planner JSON immediately instead of letting it silently corrupt state downstream.
- `python-dotenv` for API keys (Groq + Tavily).
- `httpx` only if you need raw HTTP calls beyond the SDKs.

**Frontend — minimal, per the trim**

- Default: no frontend, just `rich`-powered console output (colored step-by-step progress — doubles as demo screenshots).
- If time allows: one static HTML page + vanilla JS hitting a single FastAPI endpoint, response rendered on return (no streaming, no websockets).
- Only if Phases 0–9 finish early with slack time: FastAPI Server-Sent Events (SSE) for live-updating progress. Skip websockets entirely.

**Logging**

- Plain `json` module → dump one file to `logs/{timestamp}.json` per run. No logging framework.

**Dev/Testing**

- `pytest` for planner JSON parsing + orchestrator dependency-ordering tests.
- `uv` or plain `pip` + `venv`, whichever you already know.

**Minimal dependency list**

```
fastapi
uvicorn
pydantic
groq
tavily-python
python-dotenv
rich
pytest
```

**Known risk to call out explicitly (put this in your README's Limitations too):**
LLMs — including 70B/120B-class ones — can reason correctly about *which spec category matters more* (VRAM vs clock speed for ML, etc.) but cannot be trusted to know *exact SKU-vs-SKU rankings* (e.g. RTX 4060 vs RTX 4050) from parametric memory alone, since that's staleness/hallucination risk, not a model-size problem. The fix is grounding: pull real numbers via Tavily search or a small hardcoded reference table before the Performance executor reasons over them, rather than trusting memorized rankings.

---

## Phase 0 — Setup

- [X] Create repo/folder structure:
  ```
  backend/
  ├── main.py
  ├── planner.py
  ├── orchestrator.py
  ├── assembler.py
  ├── state.py
  ├── executors/
  │   ├── specs.py
  │   ├── pricing.py
  │   └── performance.py
  ├── tools/
  │   ├── web_search.py
  │   └── spec_lookup.py      # optional hardcoded tier-table tool, see Tech Stack note above
  └── logs/
  ```
- [X] `venv`/`uv` setup, install dependency list above
- [X] Create Groq API key + Tavily API key, add both to `.env`
- [X] Confirm `.gitignore` excludes `.env`
- [X] Smoke-test both SDKs standalone (one Groq completion call, one Tavily search call) before writing any app logic

---

## Phase 1 — Shared State Schema

- [X] Define state as a **Pydantic model** in `state.py`, e.g.:
  ```python
  from pydantic import BaseModel
  from typing import Optional

  class ProductState(BaseModel):
      specs: Optional[dict] = None
      pricing: Optional[dict] = None
      performance: Optional[dict] = None

  class AppState(BaseModel):
      user_prompt: str
      priority: str
      budget: Optional[int] = None
      products: dict[str, ProductState] = {}
      plan: list = []
      completed_steps: list = []
  ```
- [X] Write a simple `StateStore` class/functions: `get()`, `update(key, value)`, `dump_json()`
- [X] Confirm this state object is what gets passed between planner → orchestrator → executors → assembler

---

## Phase 2 — Planner Module

- [X] Write the planner prompt template (target model: `llama-3.3-70b-versatile`) — must instruct the LLM to:
  - Extract the product names/category from the user's natural language prompt
  - Output a **numbered subtask list** in strict JSON (not prose)
  - Include a `depends_on` field per subtask (list of step IDs)
- [X] Decide the fixed subtask *types* the planner can choose from: `identify_products`, `collect_specs`, `collect_pricing`, `analyze_performance`, `generate_recommendation`
- [X] Implement `planner.py`: takes `user_prompt` → calls Groq (`llama-3.3-70b-versatile`) → parses JSON → returns list of subtask objects
- [X] Add a JSON-parsing safety net (strip markdown fences, retry once on malformed JSON)
- [X] **Test:** run the planner on 3 different prompts and confirm the plans differ (different step count/order) — save these 3 outputs as evidence for your report/demo

---

## Phase 3 — Tool Layer

- [X] Implement `tools/web_search.py` using **Tavily**: `search(query: str) -> structured_result`
  - Return: title, content/snippet, source URL (for traceability) — Tavily gives you this natively
- [X] (Optional but recommended) implement `tools/spec_lookup.py`: an LLM-assisted hardware benchmark evaluation tool powered by `llama-3.1-8b-instant` (no fragile keyword string matching), consulted before Performance executor reasons — removes SKU-hallucination risk
- [X] Add a thin wrapper so every executor calls `search()` the same way, just with different queries
- [X] Test the tool standalone with 2–3 sample queries before wiring it into executors

---

## Phase 4 — Executors

### Executor 1 — Specs Collector (`executors/specs.py`)

- [X] Model: `llama-3.1-8b-instant`
- [X] Input: product name
- [X] Searches for official specifications (CPU/GPU/RAM/Display/Battery for laptops; chipset/camera/battery/display for phones)
- [X] Output: structured dict written into `state.products[name].specs`
- [X] Test on 2 laptops + 2 phones independently

### Executor 2 — Pricing (`executors/pricing.py`)

- [X] Model: `llama-3.1-8b-instant`
- [X] Input: product name (+ optionally budget from state, for filtering/flagging over-budget items)
- [X] Searches current price (India-specific query)
- [X] Output: price + source, written to `state.products[name].pricing`
- [X] Test on same sample products

### Executor 3 — Performance (`executors/performance.py`)

- [X] Model: `llama-3.3-70b-versatile`
- [X] Input: **the specs already collected** (this is your "step 2 uses step 1's output" proof — no new search for raw specs)
- [X] Reasons from CPU/GPU/RAM (already in state) to produce a qualitative verdict: gaming score, ML/photography suitability, thermal notes
- [X] For exact SKU-vs-SKU comparisons, ground via LLM-assisted `spec_lookup` tool — do not trust memorized rankings (see Tech Stack risk note)
- [X] Output written to `state.products[name].performance`
- [X] **Verify explicitly:** confirm in code/logs that this executor reads `state.products[name].specs` and does NOT call the web search tool again for raw specs — this is the single most important thing to get right for the assignment's minimum bar
- [X] Write a short "executor interface" doc (1 page): what each executor takes in, what it returns, what part of state it writes to

---

## Phase 5 — Orchestrator

- [X] Implement `orchestrator.py`:
  - Takes the plan (list of subtasks with `depends_on`)
  - Executes subtasks **in dependency order** (topological — a step only runs once its `depends_on` steps are marked complete in state)
  - Sequential execution flow
  - After each step: update `completed_steps`, print/log progress via `rich` (`[✔] Specs collected for Legion 5`)
- [X] Test the orchestrator on saved test plans — confirm it runs steps in the right order and skips nothing

---

## Phase 6 — Assembler

- [X] Implement `assembler.py`:
  - Model: `llama-3.3-70b-versatile` via Groq + `KeyManager`
  - Input: full shared state (all products' specs/pricing/performance) + user's stated priority & budget
  - Prompt the LLM to synthesize a final recommendation that **weights criteria by priority** (e.g. emphasize GPU/RAM/VRAM for "ML", camera for "photography")
  - Output: final written recommendation, side-by-side matrix, and clear buying verdict
- [X] Test end-to-end execution — confirm the recommendation weighs user priority and budget compliance

---

## Phase 7 — Main Entry Point / Output

- [X] Wire `main.py` (FastAPI app): user_prompt → planner → orchestrator (runs executors per plan) → assembler → return/print final answer
- [X] Add plain console progress output via `rich` as steps complete
- [ ] (Optional, only if time remains) wrap this in a minimal single static HTML + vanilla JS page hitting the one FastAPI endpoint — no websockets/polling
- [ ] (Optional, only if Phases 0–9 done early) upgrade to FastAPI SSE for live-updating progress

---

## Phase 8 — Logging

- [X] After each run, dump a single JSON file to `logs/{timestamp}.json` containing:
  - `user_prompt`, `generated_plan`, `executor_outputs`, `final_recommendation`, `execution_time`
- [X] Confirm you can point to these logs during your demo/report as evidence of dynamic planning

---

## Phase 9 — Testing

Run and save output/logs for all of these:

- [X] "Compare three laptops for AI development under ₹90,000."
- [X] "Compare iPhone 17, Galaxy S26, and OnePlus 15 for photography."
- [X] "Recommend the best laptop under ₹1,00,000 for gaming."
- [X] One deliberately different-shaped prompt (e.g. only 2 products, or no budget given) to further prove the plan isn't hardcoded

For each, verify:

- [X] Plan differs meaningfully across prompts
- [X] Performance executor visibly reused specs executor's output (check logs)
- [X] Final recommendation shifts emphasis based on stated priority
- [X] `pytest` suite passes (planner JSON parsing, orchestrator dependency ordering)

---

## Phase 10 — Documentation (README)

- [X] Problem statement — why product comparison is a good fit for plan-and-execute
- [X] Why Plan-and-Execute — brief note citing Wang et al. 2023 (Plan-and-Solve) as the conceptual origin, and clarify your system extends it into a multi-agent version
- [X] Tech stack section — Groq (model-per-role table above), Tavily, FastAPI + Pydantic, rich, JSON logging
- [X] Architecture diagram (User → Planner → Orchestrator → Executors → Shared State → Assembler → Final Answer)
- [X] Dependency graph diagram (Identify → Specs → {Performance, Pricing} → Recommendation)
- [X] Verification run output logs saved in `backend/logs/`
- [X] **Limitations** — include the SKU-ranking hallucination risk and how it's mitigated (grounded via search/lookup tool, not trusted from parametric knowledge), plus: sequential only, single search tool, 2 categories, no re-planning/reflection loop
- [X] Future work — parallel execution, more categories, replanning on executor failure

---

## Phase 11 — Demo Prep (4–5 min)

- [X] 0:30 — Problem introduction
- [X] 0:45 — Architecture overview (show the diagram)
- [X] 1:30 — Planner generating a plan live, on stage, for a prompt you haven't shown before
- [X] 1:30 — Executors running (console output scrolling is enough proof; Groq's speed will make this feel snappy)
- [X] 0:45 — Final recommendation + wrap-up, tie back to "this is dynamic, not hardcoded" using the 3 differing plans from Phase 2 as backup evidence if asked

---

## Suggested Build Order (start-to-finish guidance)

1. **Phase 0 first, fully.** Don't write app logic until a raw Groq call and a raw Tavily call both work standalone in a scratch script. This is the cheapest place to catch API/key/env issues.
2. **Phase 1 next.** Lock the Pydantic state schema before anything else touches it — every later phase reads/writes this shape, and changing it mid-build cascades.
3. **Phase 2 (Planner) in isolation.** Get it producing valid JSON plans for 3 varied prompts before building the orchestrator around it — you need to trust its output shape first.
4. **Phase 3 (Tools) in isolation**, same reasoning — test `search()` and (optionally) `spec_lookup()` with real queries before any executor calls them.
5. **Phase 4 (Executors) one at a time**, each tested standalone against 2 sample products before wiring into the orchestrator. Build Specs → Pricing → Performance in that order, since Performance depends on Specs' output shape.
6. **Phase 5 (Orchestrator)** once all 3 executors work standalone — wire dependency-ordered execution against your saved Phase 2 plans.
7. **Phase 6 (Assembler)** — by now state is populated end-to-end from a real run, so you can prompt-tune the synthesis against real data instead of mocked data.
8. **Phase 7 (main.py/output)** ties it together into one runnable command/endpoint.
9. **Phase 8 (Logging)** — trivial to add once Phase 7 works, but do it before Phase 9 so your test runs produce evidence automatically.
10. **Phase 9 (Testing)** — run all 4 required prompts, save every log, sanity-check the three verification bullets for each.
11. **Phase 10 (README) and Phase 11 (Demo prep)** last, once behavior is stable — write docs against what the system actually does, not what you planned.

**Cut list — do not build these** (explicitly out of scope):

- ❌ 4th category (GPUs/headphones)
- ❌ 4th executor (Software/ecosystem/warranty)
- ❌ Real async/parallel execution
- ❌ Live polling/websocket frontend
- ❌ Structured logging framework (a JSON dump per run is enough)
- ❌ Provider abstraction layer (LiteLLM etc.) — call Groq SDK directly
