import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import json
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
import config
from ingestion.loader import load_scenario
from ingestion.event_stream import EventStream
from state.customer_state import default_state
from orchestration.graph import route_event, run_pipeline
from memory.episodic_memory import EpisodicMemory
from evaluation.evaluator import Evaluator
import agents.transaction_agent as tx_agent
import agents.usage_agent as usage_agent

def hitl_terminal(result: dict) -> str:
    print('\n' + '=' * 60)
    print('  ⚠️  HUMAN REVIEW REQUIRED')
    print('=' * 60)
    print(f"  Customer   : {result['customer_id']}")
    print(f"  As of      : {result['as_of_time'][:10]}")
    print(f"  State      : {result['inferred_state']} ({result['confidence_band']} confidence)")
    print(f"  Action     : {result['action']}")
    if result.get('action_subtype'):
        print(f"  Subtype    : {result['action_subtype']}")
    print()
    print('  Why:')
    for r in result.get('reasoning', []):
        print(f'    • {r}')
    print()
    print('  Evidence:')
    for ev in result.get('evidence', []):
        print(f"    [{ev['source']}] {ev['finding']}: {ev['detail']}")
    print()
    guardrail_flags = result.get('guardrail_flags', [])
    print(f"  Guardrails : {('PASS' if not guardrail_flags else 'FLAGS: ' + str(guardrail_flags))}")
    print()
    print('  [A] Approve   [R] Reject   [M] Modify')
    choice = input('  Your decision: ').strip().upper()
    if choice == 'A':
        return 'human_approved'
    elif choice == 'R':
        return 'human_rejected'
    elif choice == 'M':
        return 'human_modified'
    return 'human_approved'

def main():
    parser = argparse.ArgumentParser(description='Customer 360 Agentic System')
    parser.add_argument('--scenario', type=str, required=True, help='Path to scenario directory (e.g. ../scenario_01)')
    parser.add_argument('--hitl', action='store_true', help='Enable terminal-mode HITL (pauses for approval)')
    args = parser.parse_args()
    scenario_dir = os.path.abspath(args.scenario)
    logger.info(f'Loading scenario from: {scenario_dir}')
    scenario = load_scenario(scenario_dir)
    entities = scenario['entities']
    customer_id = entities['customer_id']
    logger.info(f"Customer: {entities['profile']['name']} ({customer_id})")
    state = default_state(customer_id, entities['profile'], entities['accounts'])
    logger.info('Computing baselines from history_seed...')
    tx_agent.compute_baselines(state, scenario['history_seed'])
    usage_agent.compute_usage_baseline(state, scenario['history_seed'])
    logger.info(f"  Baseline income: ${state['transaction']['baseline_income']:.0f}  |  Baseline logins/week: {state['usage']['baseline_logins_per_week']:.1f}")
    ground_truth = scenario['ground_truth']
    checkpoints = ground_truth.get('checkpoints', [])
    checkpoint_times = [cp['as_of_time'] for cp in checkpoints]
    episodic = EpisodicMemory()
    evaluator = Evaluator(ground_truth)
    trace = []
    checkpoint_idx = 0
    results = []
    stream = EventStream(scenario['live_stream'])
    logger.info(f'Processing {len(stream)} live events over {len(checkpoints)} checkpoints...')
    for event in stream:
        event_time = event['timestamp']
        while checkpoint_idx < len(checkpoint_times) and event_time >= checkpoint_times[checkpoint_idx]:
            cp_time = checkpoint_times[checkpoint_idx]
            logger.info(f'  ── Checkpoint: {cp_time[:10]} ──')
            result = run_pipeline(state, cp_time, episodic, existing_trace=trace)
            if args.hitl and result.get('hitl_status') == 'escalated':
                decision = hitl_terminal(result)
                result['hitl_status'] = decision
                if decision == 'human_rejected':
                    result['action'] = 'no_action'
            score = evaluator.evaluate_checkpoint(result, checkpoint_idx)
            results.append(result)
            episodic.record(customer_id, result, ground_truth.get('scenario_id'))
            checkpoint_idx += 1
        route_event(event, state, trace)
    while checkpoint_idx < len(checkpoint_times):
        cp_time = checkpoint_times[checkpoint_idx]
        result = run_pipeline(state, cp_time, episodic, existing_trace=trace)
        score = evaluator.evaluate_checkpoint(result, checkpoint_idx)
        results.append(result)
        episodic.record(customer_id, result, ground_truth.get('scenario_id'))
        checkpoint_idx += 1
    evaluator.print_summary()
    os.makedirs(config.LOG_DIR, exist_ok=True)
    results_path = os.path.join(config.LOG_DIR, f'results_{customer_id}.json')
    trace_path = os.path.join(config.LOG_DIR, f'trace_{customer_id}.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    with open(trace_path, 'w') as f:
        json.dump(trace, f, indent=2, default=str)
    logger.info(f'Results  → {results_path}')
    logger.info(f'Trace    → {trace_path}')
if __name__ == '__main__':
    main()