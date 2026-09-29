class Evaluator:

    def __init__(self, ground_truth: dict):
        self.ground_truth = ground_truth
        self.checkpoints = ground_truth.get('checkpoints', [])
        self.red_herrings = ground_truth.get('false_positive_checks', [])
        self.results = []

    def evaluate_checkpoint(self, system_output: dict, checkpoint_idx: int) -> dict:
        if checkpoint_idx >= len(self.checkpoints):
            return {'error': 'checkpoint index out of range'}
        expected = self.checkpoints[checkpoint_idx]
        score = {}
        score['state_correct'] = system_output.get('inferred_state') == expected.get('expected_inferred_state')
        score['confidence_correct'] = system_output.get('confidence_band') == expected.get('expected_confidence_band')
        score['action_correct'] = system_output.get('action') == expected.get('expected_action')
        total = sum([score['state_correct'], score['confidence_correct'], score['action_correct']])
        score['total_points'] = total
        score['max_points'] = 3
        score['as_of_time'] = expected['as_of_time']
        score['expected'] = {'inferred_state': expected.get('expected_inferred_state'), 'confidence_band': expected.get('expected_confidence_band'), 'action': expected.get('expected_action')}
        score['got'] = {'inferred_state': system_output.get('inferred_state'), 'confidence_band': system_output.get('confidence_band'), 'action': system_output.get('action')}
        score['notes'] = expected.get('notes', '')
        self.results.append(score)
        return score

    def check_false_positive(self, triggered_action: str, event_id: str, window_events: list) -> dict:
        for rh in self.red_herrings:
            if rh['event_id'] == event_id:
                if triggered_action in rh.get('must_not_trigger_action', []):
                    return {'false_positive': True, 'event_id': event_id, 'forbidden_action': triggered_action, 'notes': rh.get('notes', '')}
        return {'false_positive': False, 'event_id': event_id}

    def print_summary(self):
        if not self.results:
            print('No checkpoints evaluated.')
            return
        total_pts = sum((r['total_points'] for r in self.results))
        max_pts = sum((r['max_points'] for r in self.results))
        pct = total_pts / max_pts * 100 if max_pts > 0 else 0
        print('\n' + '=' * 70)
        print(f"  EVALUATION RESULTS  -  {self.ground_truth.get('scenario_id', 'unknown')}")
        print('=' * 70)
        for i, r in enumerate(self.results, 1):
            print(f"\nCheckpoint {i} @ {r['as_of_time'][:10]}")
            print(f"  State  : {('PASS' if r['state_correct'] else 'FAIL')} expected={r['expected']['inferred_state']:30s} got={r['got']['inferred_state']}")
            print(f"  Conf   : {('PASS' if r['confidence_correct'] else 'FAIL')} expected={r['expected']['confidence_band']:30s} got={r['got']['confidence_band']}")
            print(f"  Action : {('PASS' if r['action_correct'] else 'FAIL')} expected={r['expected']['action']:30s} got={r['got']['action']}")
            print(f"  Score  : {r['total_points']}/{r['max_points']}")
            if r.get('notes'):
                print(f"  Notes  : {r['notes'][:80]}")
        print('\n' + '-' * 70)
        print(f'  TOTAL: {total_pts}/{max_pts} points  ({pct:.0f}%)')
        print('=' * 70 + '\n')

    def to_dict(self) -> dict:
        total_pts = sum((r['total_points'] for r in self.results))
        max_pts = sum((r['max_points'] for r in self.results))
        return {'scenario_id': self.ground_truth.get('scenario_id'), 'checkpoints': self.results, 'total_points': total_pts, 'max_points': max_pts, 'score_pct': round(total_pts / max_pts * 100, 1) if max_pts > 0 else 0}