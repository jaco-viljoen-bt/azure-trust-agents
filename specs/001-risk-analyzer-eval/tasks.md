# Tasks: Risk Analyzer Structured Evaluation

**Feature**: `001-risk-analyzer-eval` | **Date**: 2026-06-10

**Source**: [spec.md](spec.md) · [plan.md](plan.md) · [contracts/evaluate_inputs.md](contracts/evaluate_inputs.md)

---

## Phase 1 — Setup

- [x] Create `challenge-5.1/` directory
- [x] Create `challenge-5.1/requirements.txt` with pinned evaluation dependencies
- [x] Verify all required env vars are documented (fail fast at script start)

---

## Phase 2 — User Story 1: Terminal Scorecard (P1)

**Goal**: `python evaluate_risk_analyzer.py` exits 0 and prints a scorecard.

**Independent test**: Run the script and check that a table with AVERAGE row appears.

### 2.1 Cosmos DB helpers
- [x] Implement `_cosmos_containers()` returning (tx_container, cust_container)
- [x] Implement `fetch_cosmos_data(transaction_id)` → (tx_dict, cust_dict, history_list)
- [x] Handle missing transaction gracefully (skip with warning, not crash)

### 2.2 Context builder
- [x] Implement `build_context(tx, cust, history)` → human-readable string
- [x] Include all fields: amount, currency, destination, timestamp, customer profile, history count, computed risk indicators
- [x] Define `HIGH_RISK_COUNTRIES` set matching `risk_analyzer_executor`

### 2.3 Prompt builder
- [x] Implement `build_risk_prompt(context, transaction_id)` → prompt string (mirrors `risk_analyzer_executor` structure)

### 2.4 Agent invocation
- [x] Implement `invoke_risk_agent(query)` → response text (sync `AIProjectClient`)
- [x] Poll `run.status` until terminal state; return error string on non-`completed` status
- [x] Extract response from first assistant message (ascending order)

### 2.5 Dataset collection
- [x] Implement `collect_dataset()` → list of `{transaction_id, query, response, context}` rows
- [x] Iterate TX1001–TX1010; skip missing with printed warning
- [x] Print progress indicator per transaction

### 2.6 Evaluation runner
- [x] Implement `run_evaluation(dataset)` → `eval_result` dict
- [x] Write JSONL to `challenge-5.1/eval_dataset.jsonl`
- [x] Instantiate `AzureOpenAIModelConfiguration` from env vars
- [x] Call `evaluate()` with all three evaluators and correct `EvaluatorConfig` column mappings
- [x] Pass `output_path` and `fail_on_evaluator_errors=False`

### 2.7 Scorecard printer
- [x] Implement `print_scorecard(eval_result, dataset)`
- [x] Print per-transaction table (TX ID, Groundedness, Relevance, Coherence)
- [x] Print AVERAGE row from `metrics` dict
- [x] Print interpretation block (🟢 / 🟡 / 🔴 labels)

---

## Phase 3 — User Story 2: Save results.json (P2)

**Goal**: `challenge-5.1/results.json` written after every successful run.

**Independent test**: File exists and is valid JSON with required keys.

- [x] Implement `save_results(eval_result, dataset)`
- [x] Build per-transaction score map from `rows`
- [x] Merge with dataset entries (preview, context, query, full_response)
- [x] Write output matching `results.json` schema in contracts
- [x] Overwrite if exists (no append)

---

## Phase 4 — User Story 3: Interpretation Labels (P3)

**Goal**: Interpretation section printed after score table.

*(Implemented as part of `print_scorecard` in Phase 2.7 — no separate tasks needed.)*

---

## Phase 5 — Entry Point & Polish

- [x] Implement `main()` with env-var validation (fail fast with clear message)
- [x] Wire `collect_dataset → run_evaluation → save_results → print_scorecard`
- [x] Add `if __name__ == "__main__": main()` guard
- [x] Ensure script is runnable from repo root with `python challenge-5.1/evaluate_risk_analyzer.py`

---

## Dependencies

```
Phase 1 → Phase 2.1 → Phase 2.2 → Phase 2.3 → Phase 2.4 → Phase 2.5
Phase 2.5 → Phase 2.6 → Phase 2.7
Phase 2.6 → Phase 3
Phase 2.7 + Phase 3 → Phase 5
```

## Parallel Execution

- Phase 2.2 (context builder) and Phase 2.3 (prompt builder) can be written in parallel.
- Phase 2.4 (agent invocation) and Phase 2.6 (evaluation runner) can be scaffolded in parallel once 2.1 is done.
