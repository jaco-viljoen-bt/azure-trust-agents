# Contract: evaluate() Input / Output

## JSONL Input Row (eval_dataset.jsonl)

```json
{
  "transaction_id": "TX1001",
  "query": "<full risk-analysis prompt sent to the agent>",
  "response": "<agent's text response>",
  "context": "<human-readable Cosmos DB data used as groundedness context>"
}
```

## evaluate() Call

```python
evaluate(
    data="challenge-5.1/eval_dataset.jsonl",
    evaluators={
        "groundedness": GroundednessEvaluator(model_config),
        "relevance":    RelevanceEvaluator(model_config),
        "coherence":    CoherenceEvaluator(model_config),
    },
    evaluator_config={
        "groundedness": EvaluatorConfig(column_mapping={
            "response": "${data.response}",
            "context":  "${data.context}",
            "query":    "${data.query}",
        }),
        "relevance": EvaluatorConfig(column_mapping={
            "query":    "${data.query}",
            "response": "${data.response}",
        }),
        "coherence": EvaluatorConfig(column_mapping={
            "query":    "${data.query}",
            "response": "${data.response}",
        }),
    },
    output_path="challenge-5.1/results.json",
    fail_on_evaluator_errors=False,
)
```

## EvaluationResult Shape (dict-like)

```python
{
  "metrics": {
    "groundedness.groundedness": 4.1,
    "relevance.relevance":       3.8,
    "coherence.coherence":       4.3,
  },
  "rows": [
    {
      "inputs.transaction_id": "TX1001",
      "outputs.groundedness.groundedness": 4.0,
      "outputs.relevance.relevance":       4.0,
      "outputs.coherence.coherence":       5.0,
    },
    ...
  ]
}
```

## results.json Schema

```json
{
  "evaluation_timestamp": "<ISO-8601>",
  "model_judge": "gpt-4.1-mini",
  "risk_analyzer_agent_id": "<RISK_ANALYSER_AGENT_ID>",
  "transactions_evaluated": ["TX1001", ...],
  "aggregate_metrics": {
    "groundedness_avg": 4.1,
    "relevance_avg":    3.8,
    "coherence_avg":    4.3
  },
  "per_transaction": [
    {
      "transaction_id": "TX1001",
      "scores": {
        "groundedness": 4.0,
        "relevance":    4.0,
        "coherence":    5.0
      },
      "response_preview": "<first 400 chars>",
      "context": "<full context string>",
      "query": "<full prompt>",
      "full_response": "<complete agent response>"
    }
  ],
  "raw_evaluation_metrics": { ... }
}
```
