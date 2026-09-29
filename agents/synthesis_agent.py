import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
from groq import Groq
import config
_client = Groq(api_key=config.GROQ_API_KEY)
ALLOWED_STATES = {'no_significant_event', 'new_child_life_event', 'marriage_or_relationship_change', 'job_change_or_promotion', 'job_loss_or_income_disruption', 'medical_hardship', 'financial_distress_general', 'relocation', 'retirement_transition', 'wealth_growth_or_windfall', 'potential_fraud_or_takeover', 'elder_vulnerability_or_scam_risk', 'churn_risk', 'small_business_cashflow_event'}

def run_synthesis(customer_state: dict, episodic_summary: str='') -> dict:
    findings = customer_state.get('agent_findings', [])
    if not findings:
        return {'inferred_state': 'no_significant_event', 'confidence_band': 'low', 'reasoning': ['No significant findings from any agent.']}
    findings_text = _format_findings(findings)
    profile = customer_state['profile']
    prompt = f"""You are a Customer Intelligence Synthesis Agent at a bank.\n\nYou have received structured findings from specialist agents monitoring this customer.\nYour job: infer what life event or situation the customer is experiencing.\n\nCustomer Profile:\n- Name: {profile.get('name')}\n- Age: {profile.get('age')}, Occupation: {profile.get('occupation')}\n- Customer tier: {profile.get('customer_value_tier')}, Tenure: {profile.get('tenure_months')} months\n\nAgent Findings:\n{findings_text}\n\nPast Intervention History:\n{episodic_summary or 'No prior interventions.'}\n\nChoose the best fitting inferred_state from EXACTLY this list:\n- no_significant_event\n- new_child_life_event\n- marriage_or_relationship_change\n- job_change_or_promotion\n- job_loss_or_income_disruption\n- medical_hardship\n- financial_distress_general\n- relocation\n- retirement_transition\n- wealth_growth_or_windfall\n- potential_fraud_or_takeover\n- elder_vulnerability_or_scam_risk\n- churn_risk\n- small_business_cashflow_event\n\nConfidence guidelines:\n- low: 1-2 weak or ambiguous signals — possible but not confirmed\n- medium: 2-3 signals pointing in the same direction — likely\n- high: strong cross-signal evidence, e.g. income drop + healthcare + support ticket all corroborate\n\nIMPORTANT: Be careful not to infer from single isolated signals. A single large transfer or\nsingle medical purchase does not alone justify high confidence.\n\nRespond ONLY with valid JSON (no markdown):\n{{\n  "inferred_state": "<state from the list above>",\n  "confidence_band": "<low | medium | high>",\n  "reasoning": ["<concise evidence point 1>", "<concise evidence point 2>", "<concise evidence point 3>"]\n}}"""
    try:
        response = _client.chat.completions.create(model=config.LLM_MODEL, messages=[{'role': 'system', 'content': 'You are a bank customer intelligence agent. Return only valid JSON.'}, {'role': 'user', 'content': prompt}], temperature=0.1, max_tokens=512)
        text = response.choices[0].message.content.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text)
        if result.get('inferred_state') not in ALLOWED_STATES:
            result['inferred_state'] = 'no_significant_event'
        return result
    except Exception as e:
        print(f'[synthesis_agent] LLM error: {e}')
        return {'inferred_state': 'no_significant_event', 'confidence_band': 'low', 'reasoning': [f'Synthesis failed: {str(e)}']}

def _format_findings(findings: list) -> str:
    if not findings:
        return '  (none)'
    lines = []
    for f in findings:
        evidence_str = '; '.join(f.get('evidence', []))
        lines.append(f"  [{f['agent']}] {f['finding']}: value={f['value']}, confidence={f['confidence']:.0%}\n    Evidence: {evidence_str}")
    return '\n'.join(lines)