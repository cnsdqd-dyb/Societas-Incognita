"""Offline regression acceptance for material services; no model/API calls."""
import json
import unittest
from pathlib import Path


def main():
    folder = Path('reports/functional_services_20261010')
    folder.mkdir(parents=True, exist_ok=True)
    groups = []
    patterns = ['test_functional_effects.py', 'test_material_combinations.py',
                'test_twenty_mechanisms.py', 'test_mini_world.py',
                'test_material_capabilities.py', 'test_proportional_production.py',
                'test_social_content.py', 'test_interaction_controls.py']
    with (folder/'regression.log').open('w', encoding='utf-8') as log:
        for pattern in patterns:
            suite = unittest.defaultTestLoader.discover('tests', pattern=pattern)
            result = unittest.TextTestRunner(stream=log, verbosity=1).run(suite)
            item = {'group': pattern, 'tests': result.testsRun,
                    'failures': len(result.failures), 'errors': len(result.errors),
                    'skipped': len(result.skipped)}
            groups.append(item)
            print(json.dumps(item), flush=True)
    from functional_effects import KINDS
    report = {'status': 'passed' if all(not g['failures'] and not g['errors'] for g in groups) else 'failed',
              'tests': sum(g['tests'] for g in groups), 'groups': groups,
              'service_types': len(KINDS), 'model_calls': 0,
              'interrupt_resume': 'Five-round scripted run matches uninterrupted final state; returned request keys are unique.',
              'lean_scope': 'Existing bounded world_state combination actions; 20-mechanism, 3-round certificate. New functional services/security effects explicitly unsupported by the certificate adapter.',
              'limitations': ['Scripted tests do not establish discovery or social behavior by language models.',
                              'New rich configurations are not Lean-certified survival worlds.',
                              'Python compiler and floating-point execution remain trusted boundaries.']}
    (folder/'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'status': report['status'], 'tests': report['tests'], 'model_calls': 0}), flush=True)
    if report['status'] != 'passed': raise SystemExit(1)


if __name__ == '__main__': main()
