import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
from groq import Groq
import config
from state.customer_state import add_finding
HANDLED_SOURCES = {'support_logs'}
_client = Groq(api_key=config.GROQ_API_KEY)

def process_event(event: dict, state: dict):
    if event['source'] not in HANDLED_SOURCES:
        return
    event_type = event['event_type']
    payload = event['payload']
    ts = event['timestamp']
    if event_type == 'ticket_created':
        state['support']['open_tickets'] += 1
        raw_text = payload.get('raw_text', '')
        category = payload.get('category', 'general')
        analysis = _analyse_ticket(raw_text, category)
        ticket_record = {'text': raw_text, 'category': category, 'sentiment': analysis['sentiment'], 'intent': analysis['intent'], 'urgency': analysis['urgency'], 'distress_indicators': analysis.get('distress_indicators', []), 'timestamp': ts}
        state['support']['ticket_history'].append(ticket_record)
        state['support']['last_sentiment'] = analysis['sentiment']
        state['support']['last_intent'] = analysis['intent']
        state['support']['last_category'] = category
        state['support']['last_updated'] = ts
        _flag_from_analysis(analysis, state)
        _publish_findings(state)
    elif event_type == 'ticket_resolved':
        if state['support']['open_tickets'] > 0:
            state['support']['open_tickets'] -= 1
        state['support']['resolved_tickets'] += 1
        state['support']['last_updated'] = ts
        raw_text = payload.get('raw_text', '')
        resolution = payload.get('resolution_status', 'resolved')
        if resolution == 'human_rejected':
            _set_flag(state['support']['anomaly_flags'], 'complaint_rejected')
            add_finding(state, 'support_agent', 'complaint_rejected', value='human_rejected', confidence=0.85, evidence=[f"Support ticket rejected: '{raw_text[:120]}'"])

def _analyse_ticket(raw_text: str, category: str) -> dict:
    prompt = f'You are a customer support analyst at a bank. Analyse this support ticket.\n\nCategory: {category}\nTicket text: "{raw_text}"\n\nReturn ONLY valid JSON with these exact fields:\n{{\n  "sentiment": <float from -1.0 (very negative) to 1.0 (very positive)>,\n  "intent": "<payment_plan_request | complaint | inquiry | dispute | fraud_report | general>",\n  "urgency": "<low | medium | high>",\n  "distress_indicators": ["<short indicator phrase>", ...]\n}}'
    try:
        response = _client.chat.completions.create(model=config.LLM_MODEL, messages=[{'role': 'system', 'content': 'You are a banking customer support analyst. Return only valid JSON.'}, {'role': 'user', 'content': prompt}], temperature=0.1, max_tokens=256)
        text = response.choices[0].message.content.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f'[support_agent] LLM parse error: {e}')
        return {'sentiment': 0.0, 'intent': 'general', 'urgency': 'low', 'distress_indicators': []}

def _flag_from_analysis(analysis: dict, state: dict):
    sentiment = analysis.get('sentiment', 0.0)
    intent = analysis.get('intent', 'general')
    urgency = analysis.get('urgency', 'low')
    if sentiment < -0.5:
        _set_flag(state['support']['anomaly_flags'], 'negative_sentiment')
    if intent == 'payment_plan_request':
        _set_flag(state['support']['anomaly_flags'], 'payment_distress')
    if intent == 'dispute':
        _set_flag(state['support']['anomaly_flags'], 'active_dispute')
    if urgency == 'high':
        _set_flag(state['support']['anomaly_flags'], 'high_urgency_ticket')

def _publish_findings(state: dict):
    flags = state['support']['anomaly_flags']
    sentiment = state['support']['last_sentiment']
    intent = state['support']['last_intent']
    tickets = state['support']['ticket_history']
    if tickets:
        last = tickets[-1]
        add_finding(state, 'support_agent', 'ticket_analysis', value={'sentiment': sentiment, 'intent': intent}, confidence=0.88, evidence=[f"Support ticket (category: {last['category']}): '{last['text'][:100]}'", f'Sentiment: {sentiment:.2f}, Intent: {intent}'] + [f'Distress: {d}' for d in last.get('distress_indicators', [])])

def _set_flag(flag_list: list, flag: str):
    if flag not in flag_list:
        flag_list.append(flag)