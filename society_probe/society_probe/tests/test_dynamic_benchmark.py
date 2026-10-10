import copy
import unittest

from dynamic_benchmark import extrema, position, SearchLimitExceeded


class DynamicBenchmarkTests(unittest.TestCase):
    def test_state_dependent_dynamics_find_exact_paths_and_leave_input_unchanged(self):
        state = {'x': 1}
        before = copy.deepcopy(state)
        def transition(state, action):
            state['x'] = state['x'] + 1 if action == 'increment' else state['x'] * 2
            return state
        benchmark = extrema(state, 3, lambda s: ['increment', 'double'], transition, lambda s: s['x'])
        self.assertEqual((benchmark['minimum'], benchmark['maximum']), (4, 8))
        self.assertAlmostEqual(position(6, benchmark)['range_position'], .5)
        self.assertEqual(state, before)

    def test_state_constraints_change_the_benchmark(self):
        benchmark = extrema(0, 2, lambda s: [1] if s == 0 else [-1, 2],
                            lambda s, a: s + a, lambda s: s)
        self.assertEqual((benchmark['minimum'], benchmark['maximum']), (0, 3))

    def test_flat_envelope_has_no_normalized_position(self):
        benchmark = extrema(4, 2, lambda s: [0], lambda s, a: s, lambda s: s)
        self.assertIsNone(position(4, benchmark)['range_position'])
        with self.assertRaises(ValueError):
            position(5, benchmark)

    def test_incomplete_search_cannot_claim_exact_extrema(self):
        with self.assertRaises(SearchLimitExceeded):
            extrema(0, 5, lambda s: [0, 1], lambda s, a: s + a, lambda s: s, max_nodes=3)
