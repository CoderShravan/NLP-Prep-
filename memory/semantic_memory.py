ACTION_DESCRIPTIONS = {'no_action': 'No intervention — continue monitoring.', 'support_intervention': 'Proactively contact customer with a support offer (e.g. payment plan, hardship relief).', 'personalized_offer': 'Present a tailored financial product or offer based on detected life event.', 'relationship_manager_escalation': 'Route to a dedicated relationship manager for personal outreach.', 'proactive_retention_outreach': 'Reach out to the customer to address dissatisfaction and prevent churn.', 'compliance_fraud_hold': 'Place a hold on automatic actions; route to compliance/fraud team.'}
POLICY_NOTES = {'medical_hardship': 'Customer may qualify for a 90-day payment deferral and waived late fees.', 'churn_risk': 'Eligible customers can receive a fee waiver and a dedicated RM contact.', 'new_child_life_event': 'Eligible for education savings plan with 0.5% bonus rate for first year.', 'job_loss_or_income_disruption': 'Eligible for reduced-minimum-payment plan for up to 6 months.'}
MAX_DISCOUNT_PCT = 15
MAX_PAYMENT_DEFERRAL_DAYS = 90
MAX_RM_ACCOUNTS_PER_DAY = 10

def get_policy_context(inferred_state: str) -> str:
    return POLICY_NOTES.get(inferred_state, 'Standard bank policies apply.')