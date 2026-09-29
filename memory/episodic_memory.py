import sqlite3
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config

class EpisodicMemory:

    def __init__(self, db_path: str=None):
        self.db_path = db_path or config.EPISODIC_DB
        self.is_memory = self.db_path == ':memory:'
        if self.is_memory:
            self.conn = sqlite3.connect(':memory:', check_same_thread=False)
        else:
            self.conn = None
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        if self.is_memory:
            return self.conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_conn()
        with conn:
            conn.execute("\n                CREATE TABLE IF NOT EXISTS interventions (\n                    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n                    customer_id     TEXT NOT NULL,\n                    scenario_id     TEXT,\n                    as_of_time      TEXT,\n                    inferred_state  TEXT,\n                    confidence_band TEXT,\n                    action          TEXT,\n                    action_subtype  TEXT,\n                    hitl_status     TEXT,\n                    outcome         TEXT DEFAULT 'pending',\n                    evidence_json   TEXT,\n                    created_at      TEXT DEFAULT (datetime('now'))\n                )\n            ")
        if not self.is_memory:
            conn.close()

    def record(self, customer_id: str, checkpoint_result: dict, scenario_id: str=None):
        conn = self._get_conn()
        with conn:
            conn.execute('\n                INSERT INTO interventions\n                    (customer_id, scenario_id, as_of_time, inferred_state,\n                     confidence_band, action, action_subtype, hitl_status, evidence_json)\n                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ', (customer_id, scenario_id, checkpoint_result.get('as_of_time'), checkpoint_result.get('inferred_state'), checkpoint_result.get('confidence_band'), checkpoint_result.get('action'), checkpoint_result.get('action_subtype'), checkpoint_result.get('hitl_status'), json.dumps(checkpoint_result.get('evidence', []))))
        if not self.is_memory:
            conn.close()

    def get_history(self, customer_id: str) -> list:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute('\n            SELECT * FROM interventions\n            WHERE customer_id = ?\n            ORDER BY created_at DESC\n        ', (customer_id,)).fetchall()
        if not self.is_memory:
            conn.close()
        return [dict(r) for r in rows]

    def summarise_history(self, customer_id: str) -> str:
        history = self.get_history(customer_id)
        if not history:
            return 'No prior interventions recorded for this customer.'
        lines = []
        for h in history[:5]:
            lines.append(f"- [{h['as_of_time'][:10]}] State: {h['inferred_state']}, Action: {h['action']}, Outcome: {h['outcome']}")
        return '\n'.join(lines)