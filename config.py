import os
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_api_key_here")
LLM_MODEL = 'openai/gpt-oss-120b'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIOS_DIR = os.path.join(BASE_DIR, '..')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
EPISODIC_DB = os.path.join(BASE_DIR, 'memory', 'episodic.db')
INCOME_DROP_THRESHOLD = -0.25
HEALTHCARE_SINGLE_THRESHOLD = 300
HEALTHCARE_TOTAL_THRESHOLD = 2000
LARGE_OUTBOUND_THRESHOLD = 10000
SAVINGS_DRAWDOWN_THRESHOLD = 5000
LOGIN_DROP_THRESHOLD = -0.35
BABY_SPEND_THRESHOLD = 150
HITL_REQUIRED_ACTIONS = {'support_intervention', 'personalized_offer', 'relationship_manager_escalation', 'compliance_fraud_hold', 'proactive_retention_outreach'}
LOW_CONFIDENCE_SAFE_ACTIONS = {'no_action'}