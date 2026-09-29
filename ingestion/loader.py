import json
import os

def load_scenario(scenario_dir: str) -> dict:

    def read_json(filename):
        path = os.path.join(scenario_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def read_jsonl(filename):
        path = os.path.join(scenario_dir, filename)
        events = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(normalize_event(json.loads(line)))
        return events
    return {'entities': read_json('entities.json'), 'history_seed': read_jsonl('history_seed.jsonl'), 'live_stream': read_jsonl('live_stream.jsonl'), 'ground_truth': read_json('ground_truth.json'), 'replay_config': read_json('replay_config.json')}

def normalize_event(raw: dict) -> dict:
    return {'event_id': raw['event_id'], 'customer_id': raw['customer_id'], 'timestamp': raw['event_time'], 'ingestion_time': raw.get('ingestion_time', raw['event_time']), 'source': raw['source_system'], 'event_type': raw['event_type'], 'account_id': raw.get('account_id'), 'payload': raw.get('payload', {})}