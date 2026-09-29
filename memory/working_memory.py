from datetime import datetime
from state.customer_state import default_state, add_finding

class WorkingMemory:

    def __init__(self, customer_id: str, profile: dict, accounts: list):
        self._state = default_state(customer_id, profile, accounts)

    @property
    def state(self) -> dict:
        return self._state

    def update_time(self, timestamp: str):
        self._state['current_time'] = timestamp
        self._state['last_updated'] = datetime.utcnow().isoformat()

    def increment_events(self):
        self._state['events_processed'] += 1

    def add_finding(self, agent: str, finding: str, value, confidence: float, evidence: list):
        add_finding(self._state, agent, finding, value, confidence, evidence)

    def get_section(self, section: str) -> dict:
        return self._state.get(section, {})