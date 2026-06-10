# Copyright (c) Microsoft. All rights reserved.

"""
Fraud Detection Workflow - Challenge 2 (4-Executor Parallel Workflow)

Wraps the sequential_workflow_chal2.py for DevUI integration.
Architecture: Customer Data → Risk Analyzer → (Compliance Report + Fraud Alert) [parallel]
"""

import sys
from pathlib import Path

# Add challenge-2/agents to path so we can import from it
_challenge2_agents = Path(__file__).parent.parent.parent.parent / "challenge-2" / "agents"
if str(_challenge2_agents) not in sys.path:
    sys.path.insert(0, str(_challenge2_agents))

from agent_framework import WorkflowBuilder

from sequential_workflow_chal2 import (
    customer_data_executor,
    risk_analyzer_executor,
    compliance_report_executor,
    fraud_alert_executor,
)

# Build the 4-executor parallel workflow
workflow = (
    WorkflowBuilder(
        name="Fraud Detection Workflow (Challenge 2)",
        description=(
            "4-executor parallel workflow: "
            "Customer Data → Risk Analyzer → (Compliance Report + Fraud Alert)"
        ),
    )
    .set_start_executor(customer_data_executor)
    .add_edge(customer_data_executor, risk_analyzer_executor)
    .add_edge(risk_analyzer_executor, compliance_report_executor)   # parallel path 1
    .add_edge(risk_analyzer_executor, fraud_alert_executor)          # parallel path 2
    .build()
)
