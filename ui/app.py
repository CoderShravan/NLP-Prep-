import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
import streamlit as st
import config
from ingestion.loader import load_scenario
from ingestion.event_stream import EventStream
from state.customer_state import default_state
from orchestration.graph import route_event, run_pipeline
from memory.episodic_memory import EpisodicMemory
from evaluation.evaluator import Evaluator
import agents.transaction_agent as tx_agent
import agents.usage_agent as usage_agent
st.set_page_config(page_title='Customer 360 — Intervention Desk', page_icon='🏦', layout='wide')
SCENARIO_OPTIONS = {'Scenario 01 — Medical Hardship (Marcus Vance)': os.path.join(config.SCENARIOS_DIR, 'scenario_01'), 'Scenario 02 — New Child (Priya Sharma)': os.path.join(config.SCENARIOS_DIR, 'scenario_02'), 'Scenario 03 — Churn Risk (David Chen)': os.path.join(config.SCENARIOS_DIR, 'scenario_03')}
ACTION_EMOJI = {'no_action': '✅ No Action', 'support_intervention': '🆘 Support Intervention', 'personalized_offer': '🎁 Personalized Offer', 'relationship_manager_escalation': '👔 RM Escalation', 'proactive_retention_outreach': '📞 Retention Outreach', 'compliance_fraud_hold': '🚨 Compliance / Fraud Hold'}
CONFIDENCE_COLOR = {'low': '🟡', 'medium': '🟠', 'high': '🔴'}

def _init_session():
    defaults = {'scenario_loaded': False, 'scenario': None, 'state': None, 'events': [], 'event_idx': 0, 'checkpoint_times': [], 'checkpoint_idx': 0, 'checkpoint_results': [], 'trace': [], 'pending_hitl': None, 'episodic': EpisodicMemory(), 'evaluator': None, 'hitl_decisions': []}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def load_selected_scenario(scenario_dir: str):
    scenario = load_scenario(scenario_dir)
    entities = scenario['entities']
    state = default_state(entities['customer_id'], entities['profile'], entities['accounts'])
    tx_agent.compute_baselines(state, scenario['history_seed'])
    usage_agent.compute_usage_baseline(state, scenario['history_seed'])
    stream = EventStream(scenario['live_stream'])
    st.session_state.scenario = scenario
    st.session_state.state = state
    st.session_state.events = stream.events
    st.session_state.event_idx = 0
    st.session_state.checkpoint_times = [cp['as_of_time'] for cp in scenario['ground_truth'].get('checkpoints', [])]
    st.session_state.checkpoint_idx = 0
    st.session_state.checkpoint_results = []
    st.session_state.trace = []
    st.session_state.pending_hitl = None
    st.session_state.evaluator = Evaluator(scenario['ground_truth'])
    st.session_state.hitl_decisions = []
    st.session_state.scenario_loaded = True

def advance_to_next_checkpoint():
    if st.session_state.pending_hitl:
        st.warning('Please resolve the pending HITL decision before continuing.')
        return
    events = st.session_state.events
    state = st.session_state.state
    checkpoint_times = st.session_state.checkpoint_times
    checkpoint_idx = st.session_state.checkpoint_idx
    if checkpoint_idx >= len(checkpoint_times):
        st.info('All checkpoints processed.')
        return
    target_time = checkpoint_times[checkpoint_idx]
    while st.session_state.event_idx < len(events):
        event = events[st.session_state.event_idx]
        if event['timestamp'] >= target_time:
            break
        route_event(event, state, st.session_state.trace)
        st.session_state.event_idx += 1
    result = run_pipeline(state, target_time, st.session_state.episodic, existing_trace=st.session_state.trace)
    score = st.session_state.evaluator.evaluate_checkpoint(result, checkpoint_idx)
    result['score'] = score
    st.session_state.checkpoint_idx += 1
    if result.get('hitl_status') == 'escalated':
        st.session_state.pending_hitl = result
    else:
        st.session_state.checkpoint_results.append(result)
        st.session_state.episodic.record(state['customer_id'], result, st.session_state.scenario['ground_truth'].get('scenario_id'))

def render_state_board(state: dict):
    st.subheader('📋 Shared Customer State Board')
    col1, col2, col3, col4 = st.columns(4)
    tx = state['transaction']
    usage = state['usage']
    support = state['support']
    kyc = state['kyc']
    with col1:
        st.markdown('**💳 Transaction**')
        income_chg = tx.get('income_change_pct', 0)
        st.metric('Income vs Baseline', f'{income_chg * 100:.1f}%', delta=f'{income_chg * 100:.1f}%', delta_color='normal')
        st.metric('Healthcare Spend', f"${tx['healthcare_spend']:.0f}")
        st.metric('Savings Drawdown', f"${tx['savings_drawdown']:.0f}")
        if tx['anomaly_flags']:
            st.caption('🚩 ' + ', '.join(tx['anomaly_flags']))
    with col2:
        st.markdown('**📱 Usage**')
        login_chg = usage.get('login_change_pct', 0)
        st.metric('Login Freq vs Baseline', f'{login_chg * 100:.1f}%', delta=f'{login_chg * 100:.1f}%', delta_color='normal')
        st.metric('Login Trend', usage.get('login_trend', 'stable').title())
        if usage['recent_searches']:
            st.caption('🔍 ' + ', '.join((f'"{s}"' for s in usage['recent_searches'][-2:])))
        if usage['anomaly_flags']:
            st.caption('🚩 ' + ', '.join(usage['anomaly_flags']))
    with col3:
        st.markdown('**🎫 Support**')
        st.metric('Open Tickets', support['open_tickets'])
        sentiment = support.get('last_sentiment', 0)
        sentiment_label = '😊 Positive' if sentiment > 0.2 else '😠 Negative' if sentiment < -0.2 else '😐 Neutral'
        st.metric('Last Sentiment', f'{sentiment:.2f}', delta=sentiment_label)
        if support['last_intent']:
            st.caption(f"Intent: {support['last_intent']}")
        if support['anomaly_flags']:
            st.caption('🚩 ' + ', '.join(support['anomaly_flags']))
    with col4:
        st.markdown('**📑 KYC**')
        if kyc['dependents_changed']:
            st.metric('Dependents', f"{kyc['dependents_old']} → {kyc['dependents_new']}")
        else:
            st.metric('Dependents', 'No change')
        if kyc['anomaly_flags']:
            st.caption('🚩 ' + ', '.join(kyc['anomaly_flags']))

def render_hitl_panel(result: dict):
    st.markdown('---')
    st.markdown('## 🔔 Human Review Required')
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.markdown(f"**Customer:** {result['customer_id']}  |  **As of:** {result['as_of_time'][:10]}")
        st.markdown(f"**Inferred State:** `{result['inferred_state']}`  {CONFIDENCE_COLOR.get(result['confidence_band'], '⚪')} Confidence: **{result['confidence_band'].upper()}**")
        st.markdown(f"### Proposed Action: {ACTION_EMOJI.get(result['action'], result['action'])}")
        if result.get('action_subtype'):
            st.markdown(f"_Subtype: {result['action_subtype']}_")
        st.markdown('**Why this action was chosen:**')
        for r in result.get('reasoning', []):
            st.markdown(f'- {r}')
        st.markdown('**Evidence:**')
        for ev in result.get('evidence', []):
            st.markdown(f"- [{ev['source']}] **{ev['finding']}**: {ev['detail']}")
        col_p, col_g = st.columns(2)
        with col_p:
            st.markdown('**Policy checks:**')
            for check in result.get('policy_checks', []):
                st.markdown(f'✅ {check}')
        with col_g:
            st.markdown('**Guardrails:**')
            flags = result.get('guardrail_flags', [])
            if flags:
                for f in flags:
                    st.markdown(f'⚠️ {f}')
            else:
                st.markdown('✅ All passed')
        if result.get('critique_notes'):
            st.info(f"**Critique note:** {result['critique_notes']}")
    with col_right:
        st.markdown('### Decision')
        st.markdown(f'**Expected (hidden in real system):**')
        if result.get('score'):
            expected = result['score'].get('expected', {})
            st.json(expected)
        decision = st.radio('Your decision:', ['✅ Approve', '❌ Reject', '✏️ Modify'], key='hitl_radio')
        modification = None
        if decision == '✏️ Modify':
            modification = st.text_input('Modified action subtype:', value=result.get('action_subtype', ''))
        notes = st.text_area('Reviewer notes (optional):', height=80)
        if st.button('Submit Decision', type='primary'):
            _apply_hitl_decision(result, decision, modification, notes)
            st.rerun()

def _apply_hitl_decision(result: dict, decision: str, modification: str, notes: str):
    if 'Approve' in decision:
        result['hitl_status'] = 'human_approved'
    elif 'Reject' in decision:
        result['hitl_status'] = 'human_rejected'
        result['action'] = 'no_action'
    else:
        result['hitl_status'] = 'human_modified'
        if modification:
            result['action_subtype'] = modification
    result['hitl_notes'] = notes
    st.session_state.hitl_decisions.append({'checkpoint': result['as_of_time'], 'decision': result['hitl_status'], 'notes': notes})
    st.session_state.checkpoint_results.append(result)
    st.session_state.episodic.record(st.session_state.state['customer_id'], result, st.session_state.scenario['ground_truth'].get('scenario_id'))
    st.session_state.pending_hitl = None
    st.success(f"Decision recorded: {result['hitl_status']}")

def render_trace_log(trace: list):
    st.subheader('📜 Agent Trace Log')
    if not trace:
        st.caption('No events processed yet.')
        return
    for entry in reversed(trace[-30:]):
        ts = entry.get('timestamp', '')[:16].replace('T', ' ')
        etype = entry.get('type', '')
        if etype == 'event_processed':
            agent = entry.get('agent', '')
            st.caption(f"`{ts}` **{entry.get('source')}**/{entry.get('event_type')} → {agent}")
        elif etype == 'agent_output':
            agent = entry.get('agent', '')
            out = entry.get('output', {})
            st.caption(f'`{ts}` 🤖 **{agent}** → {json.dumps(out)[:80]}')
        elif etype == 'guardrail':
            out = entry.get('output', {})
            icon = '✅' if out.get('passed') else '⚠️'
            st.caption(f"`{ts}` {icon} **guardrails** → {out.get('final_action')} | flags: {out.get('flags', [])}")

def main():
    _init_session()
    st.title('🏦 Agentic Customer 360 — Proactive Intervention Desk')
    st.caption('Continuous customer monitoring with specialized agents, shared state board, and HITL approval')
    with st.sidebar:
        st.header('⚙️ Controls')
        selected = st.selectbox('Select Scenario', list(SCENARIO_OPTIONS.keys()))
        scenario_dir = SCENARIO_OPTIONS[selected]
        if st.button('Load Scenario', type='primary'):
            with st.spinner('Loading scenario and computing baselines...'):
                load_selected_scenario(scenario_dir)
            st.success('Scenario loaded!')
        st.divider()
        if st.session_state.scenario_loaded:
            state = st.session_state.state
            cp_total = len(st.session_state.checkpoint_times)
            cp_done = st.session_state.checkpoint_idx
            events_total = len(st.session_state.events)
            events_done = st.session_state.event_idx
            st.markdown(f"**Customer:** {state['profile']['name']}")
            st.markdown(f"**ID:** {state['customer_id']}")
            st.progress(events_done / max(events_total, 1), text=f'Events: {events_done}/{events_total}')
            st.progress(cp_done / max(cp_total, 1), text=f'Checkpoints: {cp_done}/{cp_total}')
            if st.button('▶️ Process to Next Checkpoint'):
                with st.spinner('Running agents and pipeline...'):
                    advance_to_next_checkpoint()
                st.rerun()
            if cp_done >= cp_total and (not st.session_state.pending_hitl):
                st.success('✅ All checkpoints processed!')
        st.divider()
        st.caption('Architecture: 4 signal agents → shared state → LangGraph pipeline → guardrails → HITL')
    if not st.session_state.scenario_loaded:
        st.info('👈 Select a scenario from the sidebar and click **Load Scenario** to start.')
        st.markdown('\n        ### How this works\n        1. **Load** a scenario — the system reads customer history to compute baselines\n        2. **Process to Next Checkpoint** — events stream in, agents update the shared state board\n        3. At each **checkpoint**, the synthesis pipeline runs and proposes an action\n        4. If the action requires **human review**, the HITL panel appears for you to Approve/Reject/Modify\n        5. Results are compared against the hidden **ground truth**\n        ')
        return
    state = st.session_state.state
    if st.session_state.pending_hitl:
        render_hitl_panel(st.session_state.pending_hitl)
        st.divider()
    render_state_board(state)
    if st.session_state.checkpoint_results:
        st.divider()
        st.subheader('📊 Completed Checkpoints')
        for result in st.session_state.checkpoint_results:
            score = result.get('score', {})
            pts = score.get('total_points', '?')
            max_pts = score.get('max_points', 3)
            action_label = ACTION_EMOJI.get(result['action'], result['action'])
            hitl_icon = '✅' if 'approved' in result.get('hitl_status', '') else '👤'
            with st.expander(f"📍 {result['as_of_time'][:10]}  |  {result['inferred_state']}  |  {action_label}  |  Score: {pts}/{max_pts}  {hitl_icon}", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown('**System output:**')
                    st.json({'inferred_state': result['inferred_state'], 'confidence_band': result['confidence_band'], 'action': result['action'], 'action_subtype': result.get('action_subtype'), 'hitl_status': result['hitl_status']})
                with c2:
                    if score:
                        st.markdown('**vs Ground Truth:**')
                        for field in ['inferred_state', 'confidence_band', 'action']:
                            got = score['got'].get(field, '?')
                            exp = score['expected'].get(field, '?')
                            icon = '✅' if got == exp else '❌'
                            st.markdown(f'{icon} {field}: got `{got}` expected `{exp}`')
                if result.get('reasoning'):
                    st.markdown('**Reasoning:**')
                    for r in result['reasoning']:
                        st.markdown(f'- {r}')
    with st.expander('📜 Agent Trace Log', expanded=False):
        render_trace_log(st.session_state.trace)
if __name__ == '__main__':
    main()