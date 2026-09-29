import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from state.customer_state import add_finding
HANDLED_SOURCES = {'loan_kyc'}

def process_event(event: dict, state: dict):
    if event['source'] not in HANDLED_SOURCES:
        return
    payload = event['payload']
    subtype = payload.get('event_subtype', event['event_type'])
    ts = event['timestamp']
    if subtype == 'dependents_change':
        old_val = payload.get('old_value')
        new_val = payload.get('new_value')
        increased = old_val is not None and new_val is not None and (int(new_val) > int(old_val))
        state['kyc']['dependents_changed'] = True
        state['kyc']['dependents_old'] = old_val
        state['kyc']['dependents_new'] = new_val
        state['kyc']['last_updated'] = ts
        if increased:
            _set_flag(state['kyc']['anomaly_flags'], 'dependents_increased')
            add_finding(state, 'kyc_agent', 'dependents_increased', value={'old': old_val, 'new': new_val}, confidence=0.98, evidence=[f'Official KYC update: dependents changed from {old_val} to {new_val}'])
    elif subtype == 'marital_status_change':
        _set_flag(state['kyc']['anomaly_flags'], 'marital_status_changed')
        state['kyc']['last_updated'] = ts
    elif subtype == 'address_change':
        _set_flag(state['kyc']['anomaly_flags'], 'address_changed')
        state['kyc']['last_updated'] = ts

def _set_flag(flag_list: list, flag: str):
    if flag not in flag_list:
        flag_list.append(flag)