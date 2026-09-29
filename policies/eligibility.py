import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

def check_eligibility(state: dict, proposed_action: str) -> dict:
    passed = []
    failed = []
    if proposed_action == 'no_action':
        return {'eligible': True, 'reason': 'No action required', 'checks_passed': [], 'checks_failed': []}
    tenure = state['profile'].get('tenure_months', 0)
    if tenure >= 3:
        passed.append(f'tenure_ok ({tenure} months)')
    else:
        failed.append(f'tenure_too_short ({tenure} months < 3)')
    tx_flags = state['transaction'].get('anomaly_flags', [])
    if 'fraud_flag' in tx_flags and proposed_action != 'compliance_fraud_hold':
        failed.append('active_fraud_flag_blocks_action')
    if proposed_action == 'personalized_offer':
        income_change = state['transaction'].get('income_change_pct', 0.0)
        if income_change < -0.5:
            failed.append(f'severe_income_drop ({income_change:.0%}) — offer may worsen distress')
        else:
            passed.append('income_ok_for_offer')
    if proposed_action == 'support_intervention':
        has_ticket = state['support']['open_tickets'] > 0 or len(state['support']['ticket_history']) > 0
        has_spend = state['transaction']['healthcare_spend'] > 0
        if has_ticket or has_spend:
            passed.append('has_support_signal')
        else:
            failed.append('no_support_signal_for_intervention')
    if proposed_action == 'relationship_manager_escalation':
        tier = state['profile'].get('customer_value_tier', 'low')
        if tier in ('mid', 'high'):
            passed.append(f'value_tier_eligible ({tier})')
        else:
            failed.append(f'value_tier_too_low ({tier}) for RM escalation')
    eligible = len(failed) == 0
    reason = 'All checks passed' if eligible else '; '.join(failed)
    return {'eligible': eligible, 'reason': reason, 'checks_passed': passed, 'checks_failed': failed}