# Research Log — Agentic Customer 360

## Source 1: Large Language Model based Multi-Agents: A Survey of Progress and Challenges
**Link:** https://arxiv.org/abs/2402.01680

**What I learned:**
- Multi-Agent Systems (MAS) divide complex tasks among specialized agents, each with a focused role
- Swarm/parallel execution is appropriate when subtasks are independent and can run concurrently
- Agent coordination patterns: parallel, sequential handoff, and critique-refiner are all valid depending on the task
- Shared state boards are recommended over isolated per-agent state to avoid contradictions
- Agent specialization improves depth of reasoning compared to one generalist agent

**Which architectural decisions it influenced:**
- Using 4 parallel specialist agents (transaction, usage, support, kyc) rather than one omniscient agent
- The shared CustomerState board design — every agent reads/writes the same dict
- Using a sequential handoff pattern for the synthesis → action → critique chain
- Critique-refiner loop: critique_agent reviews the synthesis+action output before final decision

---

## Source 2: ReAct: Synergizing Reasoning and Acting in Language Models
**Link:** https://arxiv.org/abs/2210.03629

**What I learned:**
- LLMs benefit from interleaving reasoning steps (Thought) with actions (Act) and observations (Observe)
- This "think before acting" pattern improves factual grounding and reduces hallucination
- Observation feedback loops are important — agents should update their reasoning based on new evidence

**Which architectural decisions it influenced:**
- Each LLM call (support_agent, synthesis_agent, critique_agent) is given structured observation input (agent findings) before being asked to reason
- The synthesis agent prompt explicitly shows all agent findings before asking for a conclusion — this is the "Observe before Reason" pattern
- Critique agent reviews the action proposal with the full evidence — another Observe → Reason step

---

## Source 3: MemRetriever
**Link:** https://arxiv.org/abs/2609.11951

**What I learned:**
- Long-term memory in agents benefits from structured retrieval rather than raw vector search
- Separating working memory (current context), episodic memory (past events), and semantic memory (general knowledge) improves both efficiency and accuracy
- Retrieval should be targeted — don't retrieve everything, only what's relevant to the current decision

**Which architectural decisions it influenced:**
- Three-tier memory design: working (CustomerState dict), episodic (SQLite interventions table), semantic (Python policy dicts)
- Episodic memory is queried by customer_id to retrieve only that customer's history
- Semantic memory (policy rules, offer limits) is passed as structured Python objects — no vector search needed since the data is small and structured

---

## Source 4: Transforming Business Operations with Multi-Agent Systems (AWS Blog)
**Link:** https://aws.amazon.com/blogs/industries/transforming-business-operations-with-multi-agent-systems-field-workforce-safety-ai-assistant/

**What I learned:**
- Multi-agent systems in production use deterministic routing (rules-based) for the majority of decisions
- LLMs are reserved for tasks that genuinely require natural language understanding
- Human-in-the-loop checkpoints are essential for high-stakes actions (customer-facing interventions, compliance-sensitive decisions)
- Observability (logging every agent call, decision, and handoff) is critical for debugging and audit

**Which architectural decisions it influenced:**
- Deterministic routing in graph.py — route_event() uses source_system to pick the right agent without any LLM involvement
- LLM usage is limited to three specific calls: support sentiment, life event synthesis, and critique sanity check
- HITL is implemented as a real interruption point (not just a prompt guardrail) in both UI and CLI
- Full trace log: every event, agent output, guardrail result, and HITL decision is recorded to a JSONL file

---

## Source 5: LangChain / LangGraph Documentation
**Link:** https://langchain-ai.github.io/langgraph/

**What I learned:**
- LangGraph implements agent workflows as directed graphs (nodes = agents, edges = handoffs)
- StateGraph with a shared TypedDict state is the cleanest way to pass context between agent nodes
- LangGraph supports conditional edges, which allows branching based on guardrail outcomes

**Which architectural decisions it influenced:**
- Chose LangGraph over plain Python orchestration for the reasoning pipeline (synthesis → action → critique → guardrails)
- Used StateGraph with PipelineState TypedDict — all nodes read and write the same state object
- Linear graph with END: synthesis → action → critique → guardrails → END
  (No conditional branching needed — the guardrails node always overwrites the action if needed)

---

## Source 6: Problem Statement and Provided Resources (Tanishq Ahuja)

**What I learned:**
- The evaluation criteria specifically measures: inferred_state accuracy, timeliness (correct checkpoint), action correctness
- Red herring events are explicitly included to test false-positive resistance
- The system should emit structured checkpoint outputs at specific time boundaries
- Three trigger types are expected: event trigger, time trigger, agent-dependent trigger

**Which architectural decisions it influenced:**
- Checkpoint evaluation in evaluator.py matches exactly the ground_truth.json schema
- Red herring handling: critique_agent explicitly checks for single-event over-reactions
- Cross-agent triggers: in the synthesis_agent prompt, findings from all 4 agents are combined — this is the "agent-dependent trigger" where KYC + transaction + usage together trigger a life-event inference that no single agent could make alone
- Bounded action set in action_map.py exactly matches the enum values in README_dataset_schema.md

---

## Engineering Compromises Made

1. **No true parallel agent execution**: The 4 specialist agents run sequentially per event (transaction → usage → support → kyc check). True parallel would require async or threading. For a prototype processing a few hundred events, sequential is fast enough and much simpler to debug.

2. **Vector DB omitted**: The support tickets are short enough (< 200 words) to pass directly in the LLM prompt. Adding a vector store would increase complexity with no accuracy benefit at this scale.

3. **Checkpoint-based synthesis trigger**: Rather than a fully event-driven trigger (fire synthesis whenever enough evidence accumulates), synthesis runs at the ground truth checkpoint times. This aligns with the evaluation format and is simpler to reason about.

4. **Single episodic DB for all scenarios**: The SQLite database persists across scenario runs. This is intentional — it allows the system to use previous scenario outcomes as episodic memory, demonstrating the memory architecture working across multiple customers.
