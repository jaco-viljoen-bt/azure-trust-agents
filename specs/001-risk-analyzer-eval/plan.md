# Implementation Plan: Risk Analyzer Structured Evaluation

**Branch**: `001-risk-analyzer-eval` | **Date**: 2026-06-10 | **Spec**: [spec.md](spec.md)

**Output directory**: `challenge-5.1/`

## Summary

Live-invoke the Azure AI Foundry Risk Analyzer agent for transactions TX1001–TX1010,
then score each response with `azure-ai-evaluation`'s Groundedness, Relevance, and
Coherence evaluators (LLM judge: `gpt-4.1-mini`). Print a terminal scorecard and
save `challenge-5.1/results.json`.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**:
- `azure-ai-evaluation >= 1.9.0` — `GroundednessEvaluator`, `RelevanceEvaluator`, `CoherenceEvaluator`, `evaluate()`, `AzureOpenAIModelConfiguration`
- `azure-ai-projects >= 1.0.0b12` — `AIProjectClient` (agent invocation, sync)
- `azure-ai-agents >= 1.2.0b5` — `ListSortOrder`
- `azure-cosmos` — Cosmos DB data fetch
- `azure-identity` — `DefaultAzureCredential`
- `python-dotenv` — `.env` loading

**Storage**: Azure Cosmos DB (`FinancialComplianceDB` / `Transactions` + `Customers`)

**Testing**: Manual execution + exit-code check

**Target Platform**: Linux dev container

**Project Type**: CLI evaluation script

**Performance Goals**: 10 agent calls + 30 LLM judge calls in < 5 minutes

**Constraints**:
- No cloud upload (`azure_ai_project` omitted from `evaluate()`)
- Must not crash if a transaction is missing from Cosmos DB
- `fail_on_evaluator_errors=False` keeps run alive on bad rows

**Scale/Scope**: 10 transactions × 3 evaluators = 30 LLM judge calls

## Constitution Check

No violations. Script is purely local evaluation; no shared infrastructure
modified. Credentials come from `.env`, not hardcoded.

## Project Structure

### Documentation (this feature)

```text
specs/001-risk-analyzer-eval/
├── spec.md       ✅ created
├── plan.md       ✅ this file
├── research.md   ✅ see below
├── contracts/
│   └── evaluate_inputs.md  ✅ see below
└── tasks.md      created by /speckit.tasks
```

### Source Code

```text
challenge-5.1/
├── evaluate_risk_analyzer.py   # main entry point
├── requirements.txt            # pinned deps
└── results.json                # written at runtime (git-ignored)
```

## Research Notes

### azure-ai-evaluation `evaluate()` JSONL contract

Each row must have:

| key              | used by                            |
|------------------|---------------------------------|
| `query`          | Relevance, Coherence, Groundedness |
| `response`       | all three evaluators               |
| `context`        | Groundedness only                  |
| `transaction_id` | passthrough for display            |

### Evaluator metric keys

| Evaluator    | `metrics` key                | `rows` key                          |
|--------------|------------------------------|-------------------------------------|
| Groundedness | `groundedness.groundedness`  | `outputs.groundedness.groundedness` |
| Relevance    | `relevance.relevance`        | `outputs.relevance.relevance`       |
| Coherence    | `coherence.coherence`        | `outputs.coherence.coherence`       |

### Agent invocation (sync AIProjectClient)

```python
project_client = AIProjectClient(endpoint=..., credential=DefaultAzureCredential())
with project_client:
    agents = project_client.agents
    thread  = agents.threads.create()
    agents.messages.create(thread_id=thread.id, role="user", content=query)
    run = agents.runs.create(thread_id=thread.id, agent_id=agent_id)
    while run.status in ("queued", "in_progress"):
        time.sleep(2)
        run = agents.runs.get(thread_id=thread.id, run_id=run.id)
    # collect from messages.list(order=ASCENDING)
```

### HIGH_RISK_COUNTRIES (mirrors risk_analyzer_executor)
`IR RU NG KP YE AF SY SO LY IQ MM BY VE`

### Interpretation thresholds
- ≥ 4.0 → 🟢 Strong
- ≥ 3.0 → 🟡 Adequate
- < 3.0 → 🔴 Needs improvement
