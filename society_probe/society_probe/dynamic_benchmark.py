"""Environment-independent, exact finite-horizon deterministic benchmark.

The caller supplies legal actions, a transition, and a finite scalar terminal
score. Exhaustive search gives mathematical extrema within those supplied
constraints. No LLM calls, environmental objectives, or approximate extrema.
"""
import copy
import math


class SearchLimitExceeded(RuntimeError):
    """An interrupted search must not be reported as an exact benchmark."""


def extrema(initial_state, horizon, legal_actions, transition, score, max_nodes=100000):
    """Search every legal joint-action sequence, with fixed deterministic dynamics.

    legal_actions(state) yields executable joint actions (including order when
    relevant). transition(state, action) returns the next complete state.
    score(final_state) is fixed across branches and must return a finite scalar.
    An exhausted node budget raises, rather than mislabeling sampled extrema.
    Input state and callback action objects are copied before transition.
    """
    if type(horizon) is not int or horizon < 0:
        raise ValueError('Horizon must be a nonnegative integer')
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError('Node budget must be a positive integer')
    visited = 0

    def search(state, remaining):
        nonlocal visited
        visited += 1
        if visited > max_nodes:
            raise SearchLimitExceeded('Exact search incomplete; no certified extrema returned')
        if remaining == 0:
            value = score(copy.deepcopy(state))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Score must be a finite scalar')
            return value, value, [], []
        low, high, low_path, high_path = math.inf, -math.inf, None, None
        found = False
        for action in legal_actions(copy.deepcopy(state)):
            found = True
            successor = transition(copy.deepcopy(state), copy.deepcopy(action))
            branch_low, branch_high, path_low, path_high = search(successor, remaining - 1)
            if branch_low < low:
                low, low_path = branch_low, [copy.deepcopy(action)] + path_low
            if branch_high > high:
                high, high_path = branch_high, [copy.deepcopy(action)] + path_high
        if not found:
            raise ValueError('No legal actions: model terminal states as explicit absorbing transitions')
        return low, high, low_path, high_path

    low, high, low_path, high_path = search(copy.deepcopy(initial_state), horizon)
    return {'method': 'exact_exhaustive_deterministic_search', 'horizon': horizon,
            'minimum': low, 'maximum': high, 'minimizing_actions': low_path,
            'maximizing_actions': high_path, 'visited_nodes': visited,
            'scope': 'Extrema over caller-supplied legal actions, transition, and scalar score.'}


def position(observed_score, benchmark, tolerance=1e-9):
    """Locate an admissible observed result within its exact scalar envelope.

    This is a range position, not a probability, percentile, or social approval.
    A flat envelope has no discriminating power and gets no normalized score.
    """
    if not isinstance(observed_score, (int, float)) or isinstance(observed_score, bool) or not math.isfinite(observed_score):
        raise ValueError('Observed score must be a finite scalar')
    if tolerance < 0 or not math.isfinite(tolerance):
        raise ValueError('Tolerance must be finite and nonnegative')
    if benchmark.get('method') != 'exact_exhaustive_deterministic_search':
        raise ValueError('An exact benchmark is required')
    low, high = benchmark['minimum'], benchmark['maximum']
    if observed_score < low - tolerance or observed_score > high + tolerance:
        raise ValueError('Observation outside benchmark: check state, horizon, score, and action constraints')
    gap = high - low
    return {'observed': observed_score, 'minimum': low, 'maximum': high,
            'range_position': None if gap <= tolerance else min(1., max(0., (observed_score - low) / gap)),
            'optimality_gap': high - observed_score,
            'distinguishing_power': gap > tolerance}
