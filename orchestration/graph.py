import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from datetime import datetime
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
import agents.transaction_agent as tx_agent
import agents.usage_agent as usage_agent
import agents.support_agent as support_agent
import agents.kyc_agent as kyc_agent
from agents.synthesis_agent import run_synthesis
from agents.action_agent import run_action
from agents.critique_agent import run_critique
from policies.guardrails import check_guardrails
from memory.episodic_memory import EpisodicMemory
import logging
logger = logging.getLogger(__name__)

def route_event(event: dict, state: dict, trace: list):
    source = event['source']
    ts = event['timestamp']
    agent_name = None
    if source in tx_agent.HANDLED_SOURCES:
        tx_agent.process_event(event, state)
        agent_name = 'transaction_agent'
    elif source in usage_agent.HANDLED_SOURCES:
        usage_agent.process_event(event, state)
        agent_name = 'usage_agent'
    elif source in support_agent.HANDLED_SOURCES:
        support_agent.process_event(event, state)
        agent_name = 'support_agent'
    elif source in kyc_agent.HANDLED_SOURCES:
        kyc_agent.process_event(event, state)
        agent_name = 'kyc_agent'
    state['events_processed'] += 1
    state['current_time'] = ts
    if agent_name:
        trace.append({'timestamp': ts, 'type': 'event_processed', 'event_id': event['event_id'], 'source': source, 'event_type': event['event_type'], 'agent': agent_name})
        logger.info(f"[{ts[:16]}] {event['event_id']} → {agent_name}")

class PipelineState(TypedDict):
    customer_state: dict
    synthesis_output: Optional[dict]
    action_output: Optional[dict]
    critique_output: Optional[dict]
    guardrail_output: Optional[dict]
    trace_log: List[dict]
    episodic_summary: str

def synthesis_node(state: PipelineState) -> PipelineState:
    logger.info('[pipeline] Running synthesis agent...')
    result = run_synthesis(state['customer_state'], state.get('episodic_summary', ''))
    state['customer_state']['inferred_state'] = result['inferred_state']
    state['customer_state']['confidence_band'] = result['confidence_band']
    state['customer_state']['reasoning'] = result['reasoning']
    state['synthesis_output'] = result
    state['trace_log'].append({'timestamp': datetime.utcnow().isoformat(), 'type': 'agent_output', 'agent': 'synthesis_agent', 'output': {'inferred_state': result['inferred_state'], 'confidence_band': result['confidence_band']}})
    logger.info(f"[pipeline] Synthesis → {result['inferred_state']} ({result['confidence_band']})")
    return state

def action_node(state: PipelineState) -> PipelineState:
    logger.info('[pipeline] Running action agent...')
    result = run_action(state['customer_state'])
    state['customer_state']['recommended_action'] = result['action']
    state['customer_state']['action_subtype'] = result['action_subtype']
    state['customer_state']['hitl_status'] = result['hitl_status']
    state['action_output'] = result
    state['trace_log'].append({'timestamp': datetime.utcnow().isoformat(), 'type': 'agent_output', 'agent': 'action_agent', 'output': {'action': result['action'], 'action_subtype': result['action_subtype']}})
    logger.info(f"[pipeline] Action → {result['action']} / {result['action_subtype']}")
    return state

def critique_node(state: PipelineState) -> PipelineState:
    logger.info('[pipeline] Running critique agent...')
    result = run_critique(state['customer_state'])
    if result.get('override_action') and result['override_action'] != state['customer_state']['recommended_action']:
        logger.warning(f"[pipeline] Critique override: {state['customer_state']['recommended_action']} → {result['override_action']}")
        state['customer_state']['recommended_action'] = result['override_action']
    state['critique_output'] = result
    state['trace_log'].append({'timestamp': datetime.utcnow().isoformat(), 'type': 'agent_output', 'agent': 'critique_agent', 'output': {'consistent': result['consistent'], 'flags': result.get('flags', [])}})
    return state

def guardrail_node(state: PipelineState) -> PipelineState:
    logger.info('[pipeline] Running guardrails...')
    proposed = state['customer_state']['recommended_action']
    result = check_guardrails(state['customer_state'], proposed)
    if result['final_action'] != proposed:
        logger.warning(f"[pipeline] Guardrail override: {proposed} → {result['final_action']}")
    state['customer_state']['recommended_action'] = result['final_action']
    if result['hitl_required']:
        state['customer_state']['hitl_status'] = 'escalated'
    state['guardrail_output'] = result
    state['trace_log'].append({'timestamp': datetime.utcnow().isoformat(), 'type': 'guardrail', 'agent': 'guardrails', 'output': {'passed': result['passed'], 'flags': result['flags'], 'final_action': result['final_action'], 'hitl_required': result['hitl_required']}})
    logger.info(f"[pipeline] Guardrail {('PASS' if result['passed'] else 'OVERRIDE')} → {result['final_action']}")
    return state

def _build_pipeline():
    workflow = StateGraph(PipelineState)
    workflow.add_node('synthesis', synthesis_node)
    workflow.add_node('action', action_node)
    workflow.add_node('critique', critique_node)
    workflow.add_node('guardrails', guardrail_node)
    workflow.set_entry_point('synthesis')
    workflow.add_edge('synthesis', 'action')
    workflow.add_edge('action', 'critique')
    workflow.add_edge('critique', 'guardrails')
    workflow.add_edge('guardrails', END)
    return workflow.compile()
_pipeline = _build_pipeline()

def run_pipeline(customer_state: dict, checkpoint_time: str, episodic_memory: EpisodicMemory, existing_trace: list=None) -> dict:
    episodic_summary = episodic_memory.summarise_history(customer_state['customer_id'])
    pipeline_state: PipelineState = {'customer_state': customer_state, 'synthesis_output': None, 'action_output': None, 'critique_output': None, 'guardrail_output': None, 'trace_log': existing_trace or [], 'episodic_summary': episodic_summary}
    final_state = _pipeline.invoke(pipeline_state)
    cs = final_state['customer_state']
    evidence = [{'source': f['agent'], 'finding': f['finding'], 'detail': '; '.join(f.get('evidence', []))} for f in cs.get('agent_findings', [])]
    result = {'as_of_time': checkpoint_time, 'customer_id': cs['customer_id'], 'inferred_state': cs['inferred_state'], 'confidence_band': cs['confidence_band'], 'action': cs['recommended_action'], 'action_subtype': cs.get('action_subtype'), 'hitl_status': cs['hitl_status'], 'reasoning': cs.get('reasoning', []), 'evidence': evidence, 'guardrail_flags': final_state['guardrail_output'].get('flags', []), 'critique_notes': final_state['critique_output'].get('critique_notes', ''), 'policy_checks': final_state['action_output'].get('eligibility', {}).get('checks_passed', []), 'trace_log': final_state['trace_log']}
    logger.info(f"[checkpoint {checkpoint_time[:10]}] state={result['inferred_state']} | confidence={result['confidence_band']} | action={result['action']} | hitl={result['hitl_status']}")
    return result