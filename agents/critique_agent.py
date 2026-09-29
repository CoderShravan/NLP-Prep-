import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
from groq import Groq
import config
_client = Groq(api_key=config.GROQ_API_KEY)

def run_critique(customer_state: dict) -> dict:
    findings = customer_state.get('agent_findings', [])
    inferred_state = customer_state.get('inferred_state', 'no_significant_event')
    action = customer_state.get('recommended_action', 'no_action')
    confidence = customer_state.get('confidence_band', 'low')
    reasoning = customer_state.get('reasoning', [])
    findings_text = _format_findings(findings)
    reasoning_text = '\n'.join((f'  - {r}' for r in reasoning))
    prompt = f'You are a Risk and Quality Assurance agent reviewing a customer intervention proposal.\n\nProposed decision:\n- Inferred state: {inferred_state}\n- Confidence: {confidence}\n- Recommended action: {action}\n\nEvidence used (agent findings):\n{findings_text}\n\nSynthesis reasoning:\n{reasoning_text}\n\nYour task:\n1. Check if the action is proportionate to the evidence.\n2. Identify any single-event signals that might be red herrings (e.g., a large transfer that is\n   actually a tuition payment, or a refund that looks like a windfall).\n3. Check if the confidence level is appropriate for the amount of evidence.\n\nReturn ONLY valid JSON:\n{{\n  "consistent": <true | false>,\n  "flags": ["<any concern>", ...],\n  "override_action": <null | "no_action" | "proactive_retention_outreach">,\n  "critique_notes": "<one sentence explanation>"\n}}\n\nOnly set override_action if there is a clear, specific reason to change the decision.\nDo NOT override unless you have strong evidence of a mistake.'
    try:
        response = _client.chat.completions.create(model=config.LLM_MODEL, messages=[{'role': 'system', 'content': 'You are a bank risk QA agent. Return only valid JSON.'}, {'role': 'user', 'content': prompt}], temperature=0.1, max_tokens=384)
        text = response.choices[0].message.content.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text)
        allowed = {'no_action', 'proactive_retention_outreach', 'support_intervention', 'personalized_offer', 'relationship_manager_escalation', 'compliance_fraud_hold', None}
        if result.get('override_action') not in allowed:
            result['override_action'] = None
        return result
    except Exception as e:
        print(f'[critique_agent] LLM error: {e}')
        return {'consistent': True, 'flags': [], 'override_action': None, 'critique_notes': f'Critique skipped due to error: {e}'}

def _format_findings(findings: list) -> str:
    if not findings:
        return '  (none)'
    lines = []
    for f in findings:
        evidence_str = '; '.join(f.get('evidence', []))
        lines.append(f"  [{f['agent']}] {f['finding']}: {evidence_str}")
    return '\n'.join(lines)