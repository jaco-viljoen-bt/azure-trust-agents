#!/usr/bin/env python3
"""
Challenge 5 – Structured Evaluation of the Risk Analyzer Agent
===============================================================
Runs the Azure AI Foundry Risk Analyzer agent against TX1001–TX1010 and
scores each response with three quality metrics using azure-ai-evaluation:

  • Groundedness  – are claims in the response supported by the input data?
  • Relevance     – does the response answer the risk-analysis question?
  • Coherence     – is the response logically structured and consistent?

All three evaluators use an LLM judge (gpt-4.1-mini by default).
Scores range from 1 (worst) to 5 (best).

Output
------
  Terminal : per-transaction table + aggregate averages with interpretation labels
  results.json : full per-row scores, aggregate metrics, and the raw dataset
  eval_dataset.jsonl : intermediate file consumed by evaluate()

Usage
-----
  cd challenge-5
  python evaluate_risk_analyzer.py
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from azure.ai.agents.models import ListSortOrder
from azure.ai.evaluation import (
    AzureOpenAIModelConfiguration,
    CoherenceEvaluator,
    EvaluatorConfig,
    GroundednessEvaluator,
    RelevanceEvaluator,
    evaluate,
)
from azure.ai.projects import AIProjectClient
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv(override=True)

TRANSACTIONS = [
    "TX1001", "TX1002", "TX1003", "TX1004", "TX1005",
    "TX1006", "TX1007", "TX1008", "TX1009", "TX1010",
]

_HERE = Path(__file__).parent
DATASET_FILE = _HERE / "eval_dataset.jsonl"
RESULTS_FILE = _HERE / "results.json"

# ---------------------------------------------------------------------------
# Cosmos DB helpers
# ---------------------------------------------------------------------------

def _cosmos_containers():
    client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
    db = client.get_database_client("FinancialComplianceDB")
    return db.get_container_client("Transactions"), db.get_container_client("Customers")


def _query_one(container, query: str) -> dict:
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return items[0] if items else {}


def _query_many(container, query: str) -> list:
    return list(container.query_items(query=query, enable_cross_partition_query=True))


def fetch_cosmos_data(transaction_id: str) -> tuple[dict, dict, list]:
    """Return (transaction, customer, customer_transaction_history)."""
    tx_container, cust_container = _cosmos_containers()
    tx = _query_one(tx_container, f"SELECT * FROM c WHERE c.transaction_id = '{transaction_id}'")
    if not tx:
        return {}, {}, []
    cid = tx.get("customer_id", "")
    cust = _query_one(cust_container, f"SELECT * FROM c WHERE c.customer_id = '{cid}'")
    history = _query_many(tx_container, f"SELECT * FROM c WHERE c.customer_id = '{cid}'")
    return tx, cust, history


# ---------------------------------------------------------------------------
# Prompt / context builders  (mirror risk_analyzer_executor logic)
# ---------------------------------------------------------------------------

HIGH_RISK_COUNTRIES = {
    "IR", "RU", "NG", "KP", "YE", "AF", "SY", "SO", "LY", "IQ", "MM", "BY", "VE",
}


def build_context(tx: dict, cust: dict, history: list) -> str:
    """Human-readable context string derived from raw Cosmos DB data.

    This is what the evaluator uses as the *ground truth* when scoring
    Groundedness – it represents everything the agent was given to work with.
    """
    amount = tx.get("amount", 0)
    dest = tx.get("destination_country", "N/A")
    account_age = cust.get("account_age_days", 0)
    device_trust = cust.get("device_trust_score", 1.0)

    return (
        f"Transaction {tx.get('transaction_id', 'N/A')}:\n"
        f"  Amount            : {amount} {tx.get('currency', '')}\n"
        f"  Destination       : {dest}\n"
        f"  Timestamp         : {tx.get('timestamp', 'N/A')}\n"
        f"\nCustomer {cust.get('customer_id', 'N/A')}:\n"
        f"  Name              : {cust.get('name', 'N/A')}\n"
        f"  Country           : {cust.get('country', 'N/A')}\n"
        f"  Account Age       : {account_age} days\n"
        f"  Device Trust Score: {device_trust}\n"
        f"  Past Fraud        : {cust.get('past_fraud', False)}\n"
        f"\nTransaction History: {len(history)} transaction(s) on record for this customer.\n"
        f"\nComputed Fraud Risk Indicators:\n"
        f"  High Amount (>10 000)    : {amount > 10_000}\n"
        f"  High-Risk Country        : {dest in HIGH_RISK_COUNTRIES}\n"
        f"  New Account (<30 days)   : {account_age < 30}\n"
        f"  Low Device Trust (<0.5)  : {device_trust < 0.5}\n"
        f"  Past Fraud History       : {cust.get('past_fraud', False)}\n"
    )


def build_risk_prompt(context: str, transaction_id: str) -> str:
    """Prompt sent to the Risk Analyzer agent (same structure as risk_analyzer_executor)."""
    return (
        "Based on the comprehensive fraud analysis provided below, please provide your expert "
        "regulatory and compliance risk assessment:\n\n"
        f"Analysis Data:\n{context}\n\n"
        "Please focus on:\n"
        "1. Validating the risk factors identified in the analysis\n"
        "2. Assessing the risk score and level from a regulatory perspective\n"
        "3. Providing additional AML/KYC compliance considerations\n"
        "4. Checking against sanctions lists and regulatory requirements\n"
        "5. Final recommendation on transaction approval/blocking/investigation\n"
        "6. Regulatory reporting requirements if any\n\n"
        f"Transaction ID: {transaction_id}\n\n"
        "Provide a structured risk assessment with clear regulatory justification."
    )


# ---------------------------------------------------------------------------
# Agent invocation
# ---------------------------------------------------------------------------

def invoke_risk_agent(query: str) -> str:
    """Invoke the Risk Analyser Foundry agent and return its response text."""
    project_endpoint = os.environ["AI_FOUNDRY_PROJECT_ENDPOINT"]
    agent_id = os.environ["RISK_ANALYSER_AGENT_ID"]

    project_client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
    )

    with project_client:
        agents = project_client.agents

        thread = agents.threads.create()
        agents.messages.create(thread_id=thread.id, role="user", content=query)
        run = agents.runs.create(thread_id=thread.id, agent_id=agent_id)

        # Poll until terminal state
        while run.status in ("queued", "in_progress"):
            time.sleep(2)
            run = agents.runs.get(thread_id=thread.id, run_id=run.id)

        if run.status != "completed":
            return f"[Agent run ended with non-completed status: {run.status}]"

        messages = agents.messages.list(
            thread_id=thread.id, order=ListSortOrder.ASCENDING
        )
        for msg in messages:
            if msg.role == "assistant" and msg.text_messages:
                return msg.text_messages[-1].text.value

    return "[No response received from agent]"


# ---------------------------------------------------------------------------
# Phase 1 – Collect agent responses
# ---------------------------------------------------------------------------

def collect_dataset() -> list[dict]:
    """Invoke the agent for all 10 transactions and return the evaluation rows."""
    dataset: list[dict] = []

    print("\n📥  Phase 1 – Collecting Risk Analyzer agent responses")
    print(f"     Transactions : {', '.join(TRANSACTIONS)}")
    print("-" * 70)

    for idx, tx_id in enumerate(TRANSACTIONS, 1):
        print(f"  [{idx:02d}/{len(TRANSACTIONS)}] {tx_id} ... ", end="", flush=True)

        tx, cust, history = fetch_cosmos_data(tx_id)
        if not tx:
            print("⚠  skipped – transaction not found in Cosmos DB")
            continue

        context = build_context(tx, cust, history)
        query = build_risk_prompt(context, tx_id)

        try:
            response = invoke_risk_agent(query)
            print("✅")
        except Exception as exc:
            response = f"[ERROR during agent invocation: {exc}]"
            print(f"❌  {exc}")

        dataset.append(
            {
                "transaction_id": tx_id,
                "query": query,
                "response": response,
                "context": context,
            }
        )

    return dataset


# ---------------------------------------------------------------------------
# Phase 2 – Evaluate
# ---------------------------------------------------------------------------

def run_evaluation(dataset: list[dict]) -> dict:
    """Write dataset to JSONL and run the three quality-metric evaluators."""

    # Write JSONL that evaluate() will read
    with open(DATASET_FILE, "w", encoding="utf-8") as fh:
        for row in dataset:
            fh.write(json.dumps(row) + "\n")

    print("\n📊  Phase 2 – Running quality-metric evaluation")
    print(f"     Judge model  : {os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4.1-mini')}")
    print(f"     Rows         : {len(dataset)}")
    print("-" * 70)

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_version="2024-08-01-preview",
    )

    groundedness = GroundednessEvaluator(model_config)
    relevance = RelevanceEvaluator(model_config)
    coherence = CoherenceEvaluator(model_config)

    eval_result = evaluate(
        evaluation_name=f"risk-analyzer-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        data=str(DATASET_FILE),
        evaluators={
            "groundedness": groundedness,
            "relevance": relevance,
            "coherence": coherence,
        },
        evaluator_config={
            "groundedness": EvaluatorConfig(
                column_mapping={
                    "response": "${data.response}",
                    "context": "${data.context}",
                    "query": "${data.query}",
                }
            ),
            "relevance": EvaluatorConfig(
                column_mapping={
                    "query": "${data.query}",
                    "response": "${data.response}",
                }
            ),
            "coherence": EvaluatorConfig(
                column_mapping={
                    "query": "${data.query}",
                    "response": "${data.response}",
                }
            ),
        },
        output_path=str(RESULTS_FILE),
        fail_on_evaluator_errors=False,
    )

    return eval_result


# ---------------------------------------------------------------------------
# Phase 3 – Scorecard
# ---------------------------------------------------------------------------

_METRIC_KEYS = {
    "Groundedness": "groundedness.groundedness",
    "Relevance":    "relevance.relevance",
    "Coherence":    "coherence.coherence",
}

_ROW_KEYS = {
    "Groundedness": "outputs.groundedness.groundedness",
    "Relevance":    "outputs.relevance.relevance",
    "Coherence":    "outputs.coherence.coherence",
}


def _fmt(value) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value) if value is not None else "–"


def _interpretation(avg) -> str:
    if not isinstance(avg, (int, float)):
        return "N/A"
    if avg >= 4.0:
        return "🟢 Strong"
    if avg >= 3.0:
        return "🟡 Adequate"
    return "🔴 Needs improvement"


def print_scorecard(eval_result: dict, dataset: list[dict]) -> None:
    metrics = eval_result.get("metrics", {})
    rows = eval_result.get("rows", [])

    print("\n" + "=" * 70)
    print("  RISK ANALYZER EVALUATION SCORECARD")
    print("  Scores: 1 = worst  ·  5 = best  ·  threshold ≥ 3 to pass")
    print("=" * 70)

    # Per-transaction table
    header = f"{'TX ID':<10}  {'Groundedness':>14}  {'Relevance':>10}  {'Coherence':>10}"
    print(f"\n{header}")
    print("-" * 52)

    for row in rows:
        tx_id = row.get("inputs.transaction_id", row.get("transaction_id", "?"))
        g = row.get(_ROW_KEYS["Groundedness"])
        r = row.get(_ROW_KEYS["Relevance"])
        c = row.get(_ROW_KEYS["Coherence"])
        print(f"{tx_id:<10}  {_fmt(g):>14}  {_fmt(r):>10}  {_fmt(c):>10}")

    print("-" * 52)

    # Aggregate averages
    avg_g = metrics.get(_METRIC_KEYS["Groundedness"])
    avg_r = metrics.get(_METRIC_KEYS["Relevance"])
    avg_c = metrics.get(_METRIC_KEYS["Coherence"])

    print(
        f"{'AVERAGE':<10}  {_fmt(avg_g):>14}  {_fmt(avg_r):>10}  {_fmt(avg_c):>10}"
    )
    print("=" * 70)

    # Interpretation block
    print("\n📌  Interpretation")
    print("-" * 52)
    for label, avg in [("Groundedness", avg_g), ("Relevance", avg_r), ("Coherence", avg_c)]:
        avg_str = f"{avg:.2f}/5.00" if isinstance(avg, (int, float)) else "N/A"
        print(f"  {label:<15}  {avg_str:>9}   {_interpretation(avg)}")

    print("-" * 52)
    print(f"\n  Groundedness : are claims backed by the input transaction data?")
    print(f"  Relevance    : does the response address the risk question asked?")
    print(f"  Coherence    : is the response logically structured and consistent?\n")
    print(f"💾  Full results saved to : {RESULTS_FILE}")
    print()


# ---------------------------------------------------------------------------
# Save merged results
# ---------------------------------------------------------------------------

def save_results(eval_result: dict, dataset: list[dict]) -> None:
    """Merge the evaluation results with the raw dataset and persist to results.json."""
    metrics = eval_result.get("metrics", {})
    rows = eval_result.get("rows", [])

    # Build a per-transaction score map for easy look-up
    per_tx = {}
    for row in rows:
        tx_id = row.get("inputs.transaction_id", row.get("transaction_id"))
        per_tx[tx_id] = {
            "groundedness": row.get(_ROW_KEYS["Groundedness"]),
            "relevance":    row.get(_ROW_KEYS["Relevance"]),
            "coherence":    row.get(_ROW_KEYS["Coherence"]),
        }

    # Attach scores to each dataset row
    scored_dataset = []
    for entry in dataset:
        tx_id = entry["transaction_id"]
        scores = per_tx.get(tx_id, {})
        scored_dataset.append(
            {
                "transaction_id": tx_id,
                "scores": scores,
                "response_preview": entry["response"][:400] + ("…" if len(entry["response"]) > 400 else ""),
                "context": entry["context"],
                "query": entry["query"],
                "full_response": entry["response"],
            }
        )

    output = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "model_judge": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-mini"),
        "risk_analyzer_agent_id": os.environ.get("RISK_ANALYSER_AGENT_ID", "N/A"),
        "transactions_evaluated": [r["transaction_id"] for r in dataset],
        "aggregate_metrics": {
            "groundedness_avg": metrics.get(_METRIC_KEYS["Groundedness"]),
            "relevance_avg":    metrics.get(_METRIC_KEYS["Relevance"]),
            "coherence_avg":    metrics.get(_METRIC_KEYS["Coherence"]),
        },
        "per_transaction": scored_dataset,
        "raw_evaluation_metrics": metrics,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, default=str)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  Challenge 5 – Risk Analyzer Agent Structured Evaluation")
    print(f"  Transactions : {', '.join(TRANSACTIONS)}")
    print(f"  Metrics      : Groundedness · Relevance · Coherence")
    print("=" * 70)

    # Validate required env vars early
    required = [
        "AI_FOUNDRY_PROJECT_ENDPOINT",
        "RISK_ANALYSER_AGENT_ID",
        "COSMOS_ENDPOINT",
        "COSMOS_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print("❌  Missing required environment variables:")
        for v in missing:
            print(f"     – {v}")
        sys.exit(1)

    # Phase 1: collect agent responses
    dataset = collect_dataset()

    if not dataset:
        print("❌  No data collected. Aborting.")
        sys.exit(1)

    print(f"\n✅  Collected {len(dataset)} agent response(s)")

    # Phase 2: run evaluation
    eval_result = run_evaluation(dataset)

    # Phase 3: persist + print scorecard
    save_results(eval_result, dataset)
    print_scorecard(eval_result, dataset)


if __name__ == "__main__":
    main()
