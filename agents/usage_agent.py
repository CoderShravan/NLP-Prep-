import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from datetime import datetime, timedelta
import config
from state.customer_state import add_finding
HANDLED_SOURCES = {'web_app_events'}
DISTRESS_SEARCH_KEYWORDS = ['hardship', 'payment plan', 'late payment', 'defer', 'waive fee', 'close account', 'cancel', 'struggling', "can't pay"]
BABY_SEARCH_KEYWORDS = ['education savings', 'college fund', '529', 'child insurance', 'baby', 'childcare', 'daycare']
CHURN_SEARCH_KEYWORDS = ['switch bank', 'close account', 'transfer all', 'cancel account', 'competitor', 'better rate']
CHURN_FEATURE_KEYWORDS = ['manage_standing_instructions_cancel', 'close_account', 'transfer_out']

def compute_usage_baseline(state: dict, history_events: list):
    login_times = [e['timestamp'] for e in history_events if e['source'] == 'web_app_events' and e['event_type'] == 'login']
    if not login_times:
        return
    login_times.sort()
    first = datetime.fromisoformat(login_times[0].replace('Z', '+00:00'))
    last = datetime.fromisoformat(login_times[-1].replace('Z', '+00:00'))
    weeks = max((last - first).days / 7, 1)
    state['usage']['baseline_logins_per_week'] = len(login_times) / weeks

def process_event(event: dict, state: dict):
    if event['source'] not in HANDLED_SOURCES:
        return
    event_type = event['event_type']
    payload = event['payload']
    ts = event['timestamp']
    if event_type == 'login':
        state['usage']['logins_live'].append(ts)
        _update_login_trend(state)
    elif event_type == 'search_query':
        search_text = payload.get('search_text', '').lower()
        state['usage']['recent_searches'].append(search_text)
        _classify_search(search_text, state)
    elif event_type == 'feature_used':
        feature = payload.get('feature_or_page', '')
        if any((kw in feature.lower() for kw in CHURN_FEATURE_KEYWORDS)):
            if feature not in state['usage']['feature_flags']:
                state['usage']['feature_flags'].append(feature)
            _set_flag(state['usage']['anomaly_flags'], 'churn_feature_used')
            state['transaction']['standing_instructions_cancelled'] = True
    state['usage']['last_updated'] = ts
    _publish_findings(state)

def _update_login_trend(state: dict):
    logins = state['usage']['logins_live']
    if not logins:
        return
    last_ts = datetime.fromisoformat(logins[-1].replace('Z', '+00:00'))
    cutoff = last_ts - timedelta(days=14)
    recent_logins = [l for l in logins if datetime.fromisoformat(l.replace('Z', '+00:00')) >= cutoff]
    recent_per_week = len(recent_logins) / 2
    baseline = state['usage']['baseline_logins_per_week']
    state['usage']['recent_logins_per_week'] = recent_per_week
    if baseline > 0:
        change_pct = (recent_per_week - baseline) / baseline
        state['usage']['login_change_pct'] = change_pct
        if change_pct <= config.LOGIN_DROP_THRESHOLD:
            state['usage']['login_trend'] = 'declining'
            _set_flag(state['usage']['anomaly_flags'], 'login_frequency_drop')
        elif change_pct >= 0.3:
            state['usage']['login_trend'] = 'increasing'
        else:
            state['usage']['login_trend'] = 'stable'

def _classify_search(text: str, state: dict):
    if any((kw in text for kw in DISTRESS_SEARCH_KEYWORDS)):
        _set_flag(state['usage']['anomaly_flags'], 'distress_search')
    if any((kw in text for kw in BABY_SEARCH_KEYWORDS)):
        _set_flag(state['usage']['anomaly_flags'], 'baby_related_search')
    if any((kw in text for kw in CHURN_SEARCH_KEYWORDS)):
        _set_flag(state['usage']['anomaly_flags'], 'churn_intent_search')

def _publish_findings(state: dict):
    flags = state['usage']['anomaly_flags']
    change_pct = state['usage'].get('login_change_pct', 0)
    searches = state['usage']['recent_searches']
    if 'login_frequency_drop' in flags:
        add_finding(state, 'usage_agent', 'login_frequency_drop', value=round(change_pct * 100, 1), confidence=0.8, evidence=[f"Recent: {state['usage']['recent_logins_per_week']:.1f} logins/week", f"Baseline: {state['usage']['baseline_logins_per_week']:.1f} logins/week", f'Change: {change_pct * 100:.1f}%'])
    if 'churn_feature_used' in flags:
        add_finding(state, 'usage_agent', 'churn_feature_used', value=state['usage']['feature_flags'], confidence=0.9, evidence=[f'Customer used feature: {f}' for f in state['usage']['feature_flags']])
    if searches and ('distress_search' in flags or 'baby_related_search' in flags or 'churn_intent_search' in flags):
        add_finding(state, 'usage_agent', 'intent_search', value=searches[-3:], confidence=0.85, evidence=[f"Search query: '{s}'" for s in searches[-3:]])

def _set_flag(flag_list: list, flag: str):
    if flag not in flag_list:
        flag_list.append(flag)