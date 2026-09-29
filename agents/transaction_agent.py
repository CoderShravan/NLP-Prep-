import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from datetime import datetime
import config
from state.customer_state import add_finding
HANDLED_SOURCES = {'card_payments', 'core_banking_ledger', 'ach_wire', 'instant_payments'}
HEALTHCARE_CATEGORIES = {'healthcare', 'pharmacy', 'medical'}
BABY_CATEGORIES = {'baby_products'}
SAVINGS_ACCOUNT_PREFIXES = ('ACC_SAV',)

def compute_baselines(state: dict, history_events: list):
    salary_credits = []
    for event in history_events:
        if event['source'] == 'core_banking_ledger':
            tx_type = event['payload'].get('transaction_type', '')
            amount = float(event['payload'].get('amount', 0))
            if tx_type in ('salary_credit',):
                salary_credits.append(amount)
    if salary_credits:
        recent = salary_credits[-6:] if len(salary_credits) >= 6 else salary_credits
        state['transaction']['baseline_income'] = sum(recent) / len(recent)

def process_event(event: dict, state: dict):
    source = event['source']
    if source not in HANDLED_SOURCES:
        return
    payload = event['payload']
    ts = event['timestamp']
    account_id = event.get('account_id', '')
    if source == 'card_payments':
        mcc = payload.get('mcc_category', '')
        amount = float(payload.get('amount', 0))
        if mcc in HEALTHCARE_CATEGORIES:
            state['transaction']['healthcare_spend'] += amount
            _check_healthcare_flags(state)
        if mcc in BABY_CATEGORIES:
            state['transaction']['baby_spend'] += amount
            if state['transaction']['baby_spend'] >= config.BABY_SPEND_THRESHOLD:
                _set_flag(state['transaction']['anomaly_flags'], 'baby_spend_detected')
        state['transaction']['card_purchase_count_recent'] += 1
    elif source == 'core_banking_ledger':
        tx_type = payload.get('transaction_type', '')
        amount = float(payload.get('amount', 0))
        if tx_type in ('salary_credit', 'benefits_credit', 'payroll'):
            state['transaction']['income_credits'].append((ts, amount, tx_type))
            _update_income_change(state)
            if tx_type == 'benefits_credit':
                _set_flag(state['transaction']['anomaly_flags'], 'income_type_changed_to_benefits')
        if account_id and any((account_id.startswith(p) for p in SAVINGS_ACCOUNT_PREFIXES)):
            if tx_type == 'withdrawal' or tx_type == 'internal_transfer_out':
                state['transaction']['savings_drawdown'] += amount
                if state['transaction']['savings_drawdown'] >= config.SAVINGS_DRAWDOWN_THRESHOLD:
                    _set_flag(state['transaction']['anomaly_flags'], 'savings_drawdown')
    elif source in ('ach_wire', 'instant_payments'):
        if event['event_type'] == 'outbound_transfer':
            amount = float(payload.get('amount', 0))
            counterparty = payload.get('counterparty_name', '')
            state['transaction']['large_outbound_transfers'].append({'timestamp': ts, 'amount': amount, 'counterparty': counterparty})
            if amount >= config.LARGE_OUTBOUND_THRESHOLD:
                _set_flag(state['transaction']['anomaly_flags'], 'large_outbound_transfer')
            competitor_keywords = ['Chase', 'Wells Fargo', 'Bank of America', 'Citi', 'Ext Bank']
            if any((kw.lower() in counterparty.lower() for kw in competitor_keywords)):
                _set_flag(state['transaction']['anomaly_flags'], 'transfer_to_competitor_bank')
    state['transaction']['last_updated'] = ts
    _publish_findings(state)

def _update_income_change(state: dict):
    credits = state['transaction']['income_credits']
    if not credits or state['transaction']['baseline_income'] == 0:
        return
    recent_income = sum((amt for _, amt, _ in credits))
    latest_amount = credits[-1][1]
    baseline = state['transaction']['baseline_income']
    pct = (latest_amount - baseline) / baseline
    state['transaction']['recent_income'] = latest_amount
    state['transaction']['income_change_pct'] = pct
    if pct <= config.INCOME_DROP_THRESHOLD:
        _set_flag(state['transaction']['anomaly_flags'], 'income_drop')

def _check_healthcare_flags(state: dict):
    total = state['transaction']['healthcare_spend']
    if total >= config.HEALTHCARE_TOTAL_THRESHOLD:
        _set_flag(state['transaction']['anomaly_flags'], 'healthcare_spend_high')
    elif total >= config.HEALTHCARE_SINGLE_THRESHOLD:
        _set_flag(state['transaction']['anomaly_flags'], 'healthcare_spend_moderate')

def _publish_findings(state: dict):
    flags = state['transaction']['anomaly_flags']
    income_chg = state['transaction']['income_change_pct']
    healthcare = state['transaction']['healthcare_spend']
    baby = state['transaction']['baby_spend']
    drawdown = state['transaction']['savings_drawdown']
    transfers = state['transaction']['large_outbound_transfers']
    if 'income_drop' in flags or 'income_type_changed_to_benefits' in flags:
        add_finding(state, 'transaction_agent', 'income_drop', value=round(income_chg * 100, 1), confidence=0.9 if 'income_type_changed_to_benefits' in flags else 0.75, evidence=[f"Income changed {income_chg * 100:.1f}% vs baseline ${state['transaction']['baseline_income']:.0f}", f"Latest credit: ${state['transaction']['recent_income']:.0f}", 'Transaction type: benefits_credit' if 'income_type_changed_to_benefits' in flags else 'Transaction type: salary_credit'])
    if healthcare > 0:
        add_finding(state, 'transaction_agent', 'healthcare_spend', value=round(healthcare, 2), confidence=0.85 if 'healthcare_spend_high' in flags else 0.6, evidence=[f'Cumulative healthcare+pharmacy spend: ${healthcare:.0f}'])
    if baby > 0:
        add_finding(state, 'transaction_agent', 'baby_spend', value=round(baby, 2), confidence=0.7, evidence=[f'Baby products spend: ${baby:.0f}'])
    if drawdown >= config.SAVINGS_DRAWDOWN_THRESHOLD:
        add_finding(state, 'transaction_agent', 'savings_drawdown', value=round(drawdown, 2), confidence=0.88, evidence=[f'${drawdown:.0f} withdrawn from savings account'])
    if 'transfer_to_competitor_bank' in flags and transfers:
        last = transfers[-1]
        add_finding(state, 'transaction_agent', 'competitor_bank_transfer', value=last['amount'], confidence=0.92, evidence=[f"${last['amount']:.0f} transferred to {last['counterparty']}"])

def _set_flag(flag_list: list, flag: str):
    if flag not in flag_list:
        flag_list.append(flag)