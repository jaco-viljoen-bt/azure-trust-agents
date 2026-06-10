# Feature Specification: Risk Analyzer Structured Evaluation

**Feature Branch**: `001-risk-analyzer-eval`

**Created**: 2026-06-10

**Status**: Draft

**Feature Directory**: `challenge-5.1/`

## User Scenarios & Testing

### User Story 1 – Run Evaluation and Get Terminal Scorecard (Priority: P1)

A developer runs a single Python script from `challenge-5.1/` and sees a
terminal-printed scorecard showing **Groundedness**, **Relevance**, and
**Coherence** scores for the Risk Analyzer agent's outputs across the 10
transactions TX1001–TX1010.

**Why this priority**: This is the entire end goal – a runnable evaluation
that surfaces concrete quality scores without requiring any cloud dashboard.

**Independent Test**: Running `python evaluate_risk_analyzer.py` prints a
table of per-transaction scores and aggregate averages and exits with code 0.

**Acceptance Scenarios**:

1. **Given** valid `.env` with all required variables, **When** the script is
   executed, **Then** a scorecard table is printed with one row per
   transaction and a final AVERAGE row.

2. **Given** a transaction that is not found in Cosmos DB, **When** the script
   runs, **Then** that row is skipped with a warning and the other rows are
   still evaluated.

3. **Given** the agent returns an error response, **When** the evaluators
   score it, **Then** the row shows the error gracefully (no crash) and
   `fail_on_evaluator_errors=False` keeps the run alive.

---

### User Story 2 – Save Full Results to results.json (Priority: P2)

After the scorecard is printed, the full per-transaction data (scores,
context, response previews, aggregates) is saved to `challenge-5.1/results.json`.

**Why this priority**: Enables offline analysis and comparison across runs.

**Independent Test**: After a successful run, `results.json` exists and
contains `per_transaction`, `aggregate_metrics`, and `evaluation_timestamp`
keys with valid values.

**Acceptance Scenarios**:

1. **Given** a successful evaluation run, **When** the script finishes,
   **Then** `results.json` is created/overwritten in `challenge-5.1/`.

2. **Given** `results.json` already exists from a prior run, **When** a new
   run completes, **Then** the file is overwritten with the latest results.

---

### User Story 3 – Interpret Scores with Labels (Priority: P3)

Below the score table the terminal shows an interpretation block that labels
each aggregate metric as **Strong** (≥ 4.0), **Adequate** (≥ 3.0), or
**Needs improvement** (< 3.0).

**Why this priority**: Makes the scorecard actionable for developers who
don't know the 1–5 scale intuitively.

**Independent Test**: The interpretation section is printed after every run
and contains one row per metric with the label.

**Acceptance Scenarios**:

1. **Given** an average Groundedness of 4.2, **When** the scorecard prints,
   **Then** Groundedness shows `🟢 Strong`.

2. **Given** an average Relevance of 2.8, **When** the scorecard prints,
   **Then** Relevance shows `🔴 Needs improvement`.

---

## Constraints & Requirements

- **SDK**: `azure-ai-evaluation >= 1.9.0` (already installed)
- **Agent**: Use `RISK_ANALYSER_AGENT_ID` from `.env` (live invocation, no mocks)
- **Context for Groundedness**: Raw Cosmos DB transaction + customer data
- **Transactions**: TX1001–TX1010 (first 10 in the dataset)
- **Judge model**: `gpt-4.1-mini` via `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_KEY`
- **Output directory**: `challenge-5.1/`
- **Scores**: 1 (worst) – 5 (best); threshold ≥ 3 to pass
- **No cloud upload**: `azure_ai_project` param omitted → fully local run
