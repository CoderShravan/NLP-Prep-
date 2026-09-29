import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
import logging
logging.basicConfig(level=logging.WARNING)
import config
from ingestion.loader import load_scenario
from ingestion.event_stream import EventStream
from state.customer_state import default_state
from orchestration.graph import route_event, run_pipeline
from memory.episodic_memory import EpisodicMemory
from evaluation.evaluator import Evaluator
import agents.transaction_agent as tx_agent
import agents.usage_agent as usage_agent
SCENARIO_DIRS = {'scenario_01 (Medical Hardship)': os.path.join(config.SCENARIOS_DIR, 'scenario_01'), 'scenario_02 (New Child)': os.path.join(config.SCENARIOS_DIR, 'scenario_02'), 'scenario_03 (Churn Risk)': os.path.join(config.SCENARIOS_DIR, 'scenario_03')}

def run_scenario(name: str, scenario_dir: str, episodic: EpisodicMemory) -> dict:
    print(f"\n{'=' * 60}")
    print(f'  Running: {name}')
    print(f"{'=' * 60}")
    scenario = load_scenario(scenario_dir)
    entities = scenario['entities']
    customer_id = entities['customer_id']
    state = default_state(customer_id, entities['profile'], entities['accounts'])
    tx_agent.compute_baselines(state, scenario['history_seed'])
    usage_agent.compute_usage_baseline(state, scenario['history_seed'])
    ground_truth = scenario['ground_truth']
    checkpoints = ground_truth.get('checkpoints', [])
    checkpoint_times = [cp['as_of_time'] for cp in checkpoints]
    evaluator = Evaluator(ground_truth)
    trace = []
    checkpoint_idx = 0
    checkpoint_results = []
    stream = EventStream(scenario['live_stream'])
    for event in stream:
        event_time = event['timestamp']
        while checkpoint_idx < len(checkpoint_times) and event_time >= checkpoint_times[checkpoint_idx]:
            cp_time = checkpoint_times[checkpoint_idx]
            print(f'  -> Checkpoint: {cp_time[:10]}')
            result = run_pipeline(state, cp_time, episodic, existing_trace=trace)
            checkpoint_results.append(result)
            score = evaluator.evaluate_checkpoint(result, checkpoint_idx)
            print(f"     {result['inferred_state']} ({result['confidence_band']}) -> {result['action']}  [{score['total_points']}/3]")
            episodic.record(customer_id, result, ground_truth.get('scenario_id'))
            checkpoint_idx += 1
        route_event(event, state, trace)
    while checkpoint_idx < len(checkpoint_times):
        cp_time = checkpoint_times[checkpoint_idx]
        result = run_pipeline(state, cp_time, episodic, existing_trace=trace)
        checkpoint_results.append(result)
        score = evaluator.evaluate_checkpoint(result, checkpoint_idx)
        episodic.record(customer_id, result, ground_truth.get('scenario_id'))
        checkpoint_idx += 1
    evaluator.print_summary()
    os.makedirs(config.LOG_DIR, exist_ok=True)
    output_path = os.path.join(config.LOG_DIR, f'results_{customer_id}.json')
    with open(output_path, 'w') as f:
        json.dump(checkpoint_results, f, indent=2, default=str)
    print(f'  Results saved -> {output_path}')
    return evaluator.to_dict()

def main():
    episodic = EpisodicMemory(db_path=':memory:')
    all_results = []
    for name, path in SCENARIO_DIRS.items():
        result = run_scenario(name, path, episodic)
        all_results.append(result)
    print('\n' + '=' * 60)
    print('  OVERALL EVALUATION SUMMARY')
    print('=' * 60)
    total_pts = sum((r['total_points'] for r in all_results))
    total_max = sum((r['max_points'] for r in all_results))
    for r in all_results:
        pct = round(r['score_pct'])
        bar = '#' * (pct // 10) + '-' * (10 - pct // 10)
        print(f"  {r['scenario_id']:<40s} {r['total_points']}/{r['max_points']}  {bar} {pct}%")
    print('-' * 60)
    overall_pct = round(total_pts / total_max * 100) if total_max > 0 else 0
    print(f"  {'TOTAL':<40s} {total_pts}/{total_max}  {overall_pct}%")
    print('=' * 60)
if __name__ == '__main__':
    main()