import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'scripts/subscription-routing.py'


class SubscriptionRoutingTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('subscription_routing', PATH)
        self.policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.policy)
        self.capabilities = {'models': [
            {'id': model, 'reasoning_levels': [effort], 'live': True,
             'entitled': True, 'allowed_by_policy': True}
            for model, effort in self.policy.TIERS
        ]}

    def route(self, attempts=None, **kwargs):
        return self.policy.next_attempt(attempts or [], self.capabilities, **kwargs)

    def test_default_and_bounded_escalation(self):
        attempts = []
        for expected in [0, 0, 1, 2]:
            result = self.route(attempts, correction_useful=True)
            self.assertEqual(tuple(result['route']), self.policy.TIERS[expected])
            attempts.append({'tier': expected, 'outcome': 'failed'})
        self.assertEqual(self.route(attempts)['status'], 'exhausted')

    def test_no_unhelpful_correction(self):
        result = self.route([{'tier': 0, 'outcome': 'failed'}])
        self.assertEqual(result['tier'], 1)

    def test_verified_acceptance_stops(self):
        self.assertEqual(self.route([{'tier': 0, 'outcome': 'accepted'}])['status'], 'complete')

    def test_access_failures_never_escalate(self):
        for blocker in self.policy.BLOCKERS:
            self.assertEqual(self.route(blocker=blocker)['status'], 'blocked')

    def test_sol_first_needs_reason(self):
        with self.assertRaises(ValueError):
            self.route(sol_first=True)
        self.assertEqual(self.route(sol_first=True, reason='consequential correctness')['tier'], 1)

    def test_unavailable_skips_with_reason(self):
        self.capabilities['models'][0]['reasoning_levels'] = ['low']
        result = self.route()
        self.assertEqual(result['tier'], 1)
        self.assertEqual(result['skipped'][0]['reason'], 'unsupported_effort')

    def test_no_supported_route_stops(self):
        self.capabilities['models'] = []
        self.assertEqual(self.route()['status'], 'unavailable')

    def test_invalid_or_overbudget_history_rejected(self):
        for history in [[{'tier': 9, 'outcome': 'failed'}],
                        [{'tier': 1, 'outcome': 'failed'}] * 2,
                        [{'tier': 2, 'outcome': 'failed'}, {'tier': 0, 'outcome': 'failed'}]]:
            with self.assertRaises(ValueError):
                self.route(history)

    def test_six_worker_ceiling_and_overlap(self):
        self.assertEqual(self.policy.check_lanes([['a'], ['b']], active_workers=4), [])
        self.assertTrue(self.policy.check_lanes([['a'], ['b']], active_workers=5))
        self.assertTrue(self.policy.check_lanes([['src'], ['src/a.py']]))
        self.assertTrue(self.policy.check_lanes([['src/a.py']], active_file_sets=[['src/a.py']], active_workers=1))
        self.assertTrue(self.policy.check_lanes([['src/../a']]))
        self.assertTrue(self.policy.check_lanes([['a']], active_file_sets=[['b']]))
        self.assertTrue(self.policy.check_lanes(['a.py']))


if __name__ == '__main__':
    unittest.main()
