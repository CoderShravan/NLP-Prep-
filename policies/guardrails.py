import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config
LEGAL_THREAT_KEYWORDS = ['sue', 'lawsuit', 'lawyer', 'attorney', 'court', 'legal action', 'solicitor', 'barrister', 'ombudsman', 'regulator complaint']
FRAUD_INDICATOR_KEYWORDS = ['account hacked', 'unauthorized', 'fraud', 'scam', 'phishing', 'someone else', 'not me', "wasn't me"]

def check_guardrails(state: dict, proposed_action: str) -> dict:
    flags = []
    final_action = proposed_action
    hitl_required = False
    for ticket in state['support'].get('ticket_history', []):
        raw_text = ticket.get('text', '').lower()
        if any((kw in raw_text for kw in LEGAL_THREAT_KEYWORDS)):
            flags.append('legal_threat_detected')
            final_action = 'relationship_manager_escalation'
            hitl_required = True
            break
    if 'fraud_flag' in state['transaction'].get('anomaly_flags', []):
        flags.append('active_fraud_flag')
        if final_action not in ('compliance_fraud_hold', 'relationship_manager_escalation'):
            final_action = 'compliance_fraud_hold'
        hitl_required = True
    if state.get('confidence_band') == 'low' and proposed_action not in config.LOW_CONFIDENCE_SAFE_ACTIONS:
        flags.append('low_confidence_override')
        final_action = 'no_action'
    if final_action in config.HITL_REQUIRED_ACTIONS:
        hitl_required = True
    return {'passed': len(flags) == 0, 'flags': flags, 'final_action': final_action, 'hitl_required': hitl_required}