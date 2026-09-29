import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
from groq import Groq
import config
from policies.action_map import get_action_for_state
from policies.eligibility import check_eligibility
from memory.semantic_memory import get_policy_context
_client = Groq(api_key=config.GROQ_API_KEY)

def run_action(customer_state: dict) -> dict:
    inferred_state = customer_state.get('inferred_state', 'no_significant_event')
    confidence_band = customer_state.get('confidence_band', 'low')
    action_result = get_action_for_state(inferred_state, confidence_band)
    action = action_result['action']
    subtype = action_result['action_subtype']
    eligibility = check_eligibility(customer_state, action)
    if not eligibility['eligible']:
        action = 'no_action'
        subtype = None
    policy_context = get_policy_context(inferred_state)
    if action != 'no_action' and subtype:
        subtype = _refine_subtype(customer_state, action, subtype, policy_context)
    hitl_status = _determine_hitl(action, confidence_band, customer_state)
    return {'action': action, 'action_subtype': subtype, 'hitl_status': hitl_status, 'eligibility': eligibility, 'policy_context': policy_context}

def _refine_subtype(state: dict, action: str, default_subtype: str, policy_context: str) -> str:
    findings_summary = _short_findings_summary(state.get('agent_findings', []))
    prompt = f'You are drafting the specific offer subtype for a bank customer intervention.\n\nAction decided: {action}\nDefault subtype: {default_subtype}\nPolicy context: {policy_context}\n\nCustomer signals: {findings_summary}\n\nReturn ONLY valid JSON:\n{{"refined_subtype": "<a concise snake_case label like medical_hardship_payment_plan>"}}'
    try:
        response = _client.chat.completions.create(model=config.LLM_MODEL, messages=[{'role': 'system', 'content': 'You are a bank product specialist. Return only valid JSON.'}, {'role': 'user', 'content': prompt}], temperature=0.1, max_tokens=128)
        text = response.choices[0].message.content.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text)
        return result.get('refined_subtype', default_subtype)
    except Exception:
        return default_subtype

def _determine_hitl(action: str, confidence_band: str, state: dict) -> str:
    if action == 'no_action':
        return 'auto_approved'
    if action in config.HITL_REQUIRED_ACTIONS:
        return 'escalated'
    return 'auto_approved'

def _short_findings_summary(findings: list) -> str:
    if not findings:
        return 'none'
    return '; '.join((f"{f['finding']}={f['value']}" for f in findings))