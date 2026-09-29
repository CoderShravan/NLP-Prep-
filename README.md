# Agentic Customer 360 — Proactive Intervention Desk

## Problem

Traditional Customer 360 dashboards aggregate data but don't reason about it.
A customer can simultaneously experience declining usage, negative support interactions,
and unusual transactions — but a human analyst would need to manually connect these dots.

This system continuously processes customer events, maintains an evolving state board,
identifies meaningful cross-signal patterns, and commits to a bounded intervention decision.

---

## Architecture

```
[history_seed.jsonl]  ──→  Baseline Computation
[live_stream.jsonl]   ──→  Event Stream (sorted by event_time)
                                    │
               ┌────────────────────┼───────────────────┐
               │                    │                   │
     [Transaction Agent]  [Usage Agent]  [Support Agent]  [KYC Agent]
      (pure Python)        (pure Python)   (LLM: sentiment) (pure Python)
               └────────────────────┼───────────────────┘
                                    │
                       [Shared Customer State Board]
                                    │
                         ─── LangGraph Pipeline ───
                                    │
                          [Synthesis Agent]  ← LLM: infer life event
                                    │
                          [Action Agent]     ← Deterministic rules
                                    │
                          [Critique Agent]   ← LLM: red herring check
                                    │
                          [Guardrails]       ← Deterministic hard stops
                                    │
                         ─────────────────────────
                                    │
                          [HITL Checkpoint]  ← Streamlit UI or terminal
                                    │
                     ┌──────────────┴─────────────┐
               [Approved]                    [Rejected/Modified]
                     │
              [Episodic Memory]  ← SQLite
              [Audit Trace Log]  ← JSONL
```

---

## Agent Responsibilities

| Agent | Input | Logic | LLM? |
|---|---|---|---|
| Transaction | card_payments, banking_ledger, transfers | Income baselines, healthcare spend, savings drawdown, competitor transfers | No |
| Usage | web_app_events | Login frequency trends, search intent keywords, churn feature flags | No |
| Support | support_logs | Ticket counting, LLM sentiment + intent from raw_text | **Yes** |
| KYC | loan_kyc | Dependents/marital/address change detection | No |
| Synthesis | All agent findings | Cross-signal life event inference | **Yes** |
| Action | Inferred state + eligibility | Deterministic action lookup + eligibility check + LLM subtype | Partially |
| Critique | Proposed action + evidence | Red herring detection, consistency check | **Yes** |

---

## Shared State Board

One dict per customer, written by all agents, read by all agents:

```python
{
    "customer_id": "CUST_00088",
    "profile": { ... },
    "transaction": {
        "baseline_income": 3800.0,
        "income_change_pct": -0.63,
        "healthcare_spend": 9075.0,
        "anomaly_flags": ["income_drop", "healthcare_spend_high"],
        ...
    },
    "usage": {
        "baseline_logins_per_week": 3.5,
        "recent_logins_per_week": 1.0,
        "recent_searches": ["medical hardship plan"],
        ...
    },
    "support": {
        "open_tickets": 1,
        "last_sentiment": -0.85,
        "last_intent": "payment_plan_request",
        ...
    },
    "kyc": { "dependents_changed": False, ... },
    "inferred_state": "medical_hardship",
    "confidence_band": "high",
    "recommended_action": "support_intervention",
    "agent_findings": [ ... ],      # structured evidence
    "reasoning": [ ... ],           # synthesis reasoning
}
```

---

## Memory Architecture

| Layer | Implementation | Contents |
|---|---|---|
| Working Memory | Python dict (`customer_state.py`) | Current customer state, live during processing |
| Episodic Memory | SQLite (`episodic.db`) | Past interventions: what was done, when, outcome |
| Semantic Memory | Python dicts (`memory/semantic_memory.py`) | Policy rules, offer limits, action descriptions |

**No vector database.** Support ticket text is short enough to pass directly to the LLM.
Policy knowledge fits in Python dicts. Vector retrieval adds complexity without benefit here.

---

## Trigger System

| Trigger Type | How It's Implemented |
|---|---|
| **Event Trigger** | `route_event()` in `graph.py` — each event activates the relevant agent |
| **Time Trigger** | Checkpoint times from `ground_truth.json` — pipeline fires when simulation time crosses a checkpoint |
| **Agent-Dependent** | Synthesis agent correlates all agent findings — KYC change + baby spend + income dip together trigger `new_child_life_event` inference |

---

## Guardrails (Real Code, Not Prompts)

From `policies/guardrails.py`:

```python
# Legal threat → escalate immediately
if any(kw in raw_text for kw in LEGAL_THREAT_KEYWORDS):
    final_action = "relationship_manager_escalation"
    hitl_required = True

# Active fraud flag → block all autonomous offers
if "fraud_flag" in anomaly_flags:
    final_action = "compliance_fraud_hold"
    hitl_required = True

# Low confidence → never take customer-facing action
if confidence_band == "low" and proposed_action != "no_action":
    final_action = "no_action"

# All customer-facing actions → always escalate to HITL
if final_action in HITL_REQUIRED_ACTIONS:
    hitl_required = True
```

---

## Bounded Action Set

The LLM can only produce one of these actions (enforced by `action_map.py`):

- `no_action`
- `support_intervention`
- `personalized_offer`
- `relationship_manager_escalation`
- `proactive_retention_outreach`
- `compliance_fraud_hold`

---

## Dataset (3 Scenarios)

| Scenario | Customer | Life Event | Final Action |
|---|---|---|---|
| `scenario_01` | Marcus Vance, 48 | Medical hardship — ER visit → income drops to benefits → $8,500 hospital bill | `support_intervention` |
| `scenario_02` | Priya Sharma, 33 | New child — maternity income dip → baby purchases → daycare SI → KYC dependents change | `personalized_offer` |
| `scenario_03` | David Chen, 35 | Churn risk — rejected dispute → app engagement drop → savings transferred to Chase | `relationship_manager_escalation` |

Each scenario includes **red herring events** that must NOT trigger wrong actions.

---

## How to Run

### 1. Install dependencies
```bash
cd customer360
pip install -r requirements.txt
```

### 2. Run a single scenario (CLI)
```bash
python run.py --scenario ../scenario_01
python run.py --scenario ../scenario_01 --hitl   # terminal HITL mode
```

### 3. Run the Streamlit HITL interface
```bash
streamlit run ui/app.py
```

### 4. Evaluate all 3 scenarios
```bash
python evaluation/scenarios.py
```

---

## Limitations

- Synthesis trigger is checkpoint-based rather than fully event-driven (simplification for prototype)
- No async/parallel agent execution — agents run sequentially per event
- Episodic memory outcome field defaults to "pending" — real outcomes would come from a CRM system
- Red herring detection in critique_agent depends on LLM judgment, which may vary

## Future Improvements

- Event-driven synthesis trigger (accumulate evidence score, fire when threshold crossed)
- Async parallel agent execution using asyncio
- True streaming with Kafka for real-time production scenarios
- Outcome tracking: follow up on interventions to close the episodic memory loop
- More scenarios: fraud/takeover, wealth windfall, retirement transition
