"""Reusable rational soundness theorems for a precisely scoped operator subset.

No API calls. These theorems complement existing certificates without changing
their hashes or claiming whole-interpreter correctness.
"""
import hashlib
from pathlib import Path


PROVED_OPERATORS = ('constant', 'add', 'sub', 'neg', 'min', 'max', 'mul')
FULL_OPERATORS = PROVED_OPERATORS + ('div', 'floor', 'lt', 'le', 'eq', 'truth')


def source(include_advanced=False):
    root = Path(__file__).resolve().parent
    data = (root.joinpath('composed_checker.lean').read_text('utf-8') +
            root.joinpath('interval_soundness.lean').read_text('utf-8').removeprefix('import Std\n'))
    if include_advanced:
        data += root.joinpath('interval_advanced.lean').read_text('utf-8').removeprefix('import Std\n')
    return data


def export(path, examples='', include_advanced=False):
    data = source(include_advanced) + '\n' + examples
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')
    return {'source': str(path.resolve()), 'sha256': hashlib.sha256(data.encode()).hexdigest(),
            'status': 'exported_not_checked', 'proved_operators': list(FULL_OPERATORS if include_advanced else PROVED_OPERATORS),
            'complete_operator_soundness':include_advanced,
            'scope': ('Universal rational interval soundness for all 13 checker operators and positivity. No DAG reachability or world-transition proof.' if include_advanced else
                      'Universal rational interval soundness for the listed operators and positivity. No division, floor, predicates, DAG reachability or world-transition proof.')}


def check(artifact):
    from survival_certificates import check_lean
    result = check_lean(artifact)
    if result['status'] == 'lean_checked_restricted_projection':
        result['status'] = 'lean_checked_interval_soundness' if artifact.get('complete_operator_soundness') else 'lean_checked_partial_interval_soundness'
    return result
