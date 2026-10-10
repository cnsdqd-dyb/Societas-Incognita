"""Prepare pilot templates, screen candidate worlds, and export offline evidence."""
import argparse
import copy
import json
from pathlib import Path

import schemas
import sim
import world_rule_library as library
import survival_certificates as certificates


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='reports/mini_world_v1_preparation')
    p.add_argument('--configs', default='configs/mini_world_v1_20261009')
    p.add_argument('--candidate-count', type=int, default=8)
    p.add_argument('--rounds', type=int, default=50)
    args = p.parse_args()
    target = Path(args.configs); reports = Path(args.output)
    if target.exists(): raise ValueError('Refusing to overwrite prepared templates')
    source = json.loads(Path('configs/cheap_mix_oss_v4_20261009/M2_cheap_mix_oss8_p1.json').read_text('utf-8'))
    fixture = {'definition': library.base_definition(), 'generation': {'status': 'framework_fixture_not_certified'}}
    names = []
    for pressure in (False, True):
        for visibility in ('full', 'hidden'):
            c = library.configure(source, fixture, members=4, pressure=pressure,
                                  visibility=visibility, recipes=visibility)
            c['rounds'] = args.rounds; c['require_lean_certificate'] = True
            s = sim.Society(c)
            for kind in ('act', 'communicate'):
                __import__('jsonschema').Draft202012Validator.check_schema(schemas.schema(kind, s.observe('a0'), c))
            name = 'fixture_'+visibility+'_p'+str(int(pressure)); names.append(name)
            save(target/(name+'.json'), c)
    candidates = []; successful = 0
    for seed in range(args.candidate_count):
        candidate = library.generate(seed, noise_amplitude=.15)
        c = library.configure(source, candidate); c['rounds'] = args.rounds
        # Conservative fixed schedule: minimum harvest 3*.85 >= 2 converted.
        plan = certificates.alternating_plan(c)
        for joint in plan:
            for action in joint.values():
                if action['tool'] == 'gather': action['amount'] = 3
        try:
            witness = certificates.replay(c, plan)
            success = witness['status'] == 'replayed_full_survival'; successful += success
            status = witness['status']; save(reports/f'candidate_{seed}_witness.json', witness)
        except (ValueError, KeyError, TypeError) as exc:
            success = False; status = 'tested_policy_failed'; witness = {'reason': str(exc)}
        metadata = {**candidate['generation'], 'screen_status': status, 'tested_policy_full_survival': success,
                    'lean_status': 'not_verified', 'eligible_for_research_run': False,
                    'exploration_opportunity_status': 'not_assessed'}
        save(reports/f'candidate_{seed}.json', {'definition': candidate['definition'], 'screening': metadata})
        candidates.append(metadata)
        print(json.dumps({'screened_seed': seed, 'status': status, 'formal_certificate': False}), flush=True)
    # A separate integer control exercises the initial reusable certificate checker.
    deterministic = copy.deepcopy(fixture)
    for resource in deterministic['definition']['resources'].values(): resource['decay'] = 0
    c = library.configure(source, deterministic); c['rounds'] = args.rounds
    witness = certificates.replay(c, certificates.alternating_plan(c))
    artifact = certificates.export_lean(c, witness, reports/'integer_control_survival.lean')
    checked = certificates.check_lean(artifact)
    save(reports/'integer_control_config.json', c)
    save(reports/'integer_control_witness.json', witness)
    save(reports/'integer_control_lean_check.json', checked)
    result = {'prepared_not_run': True, 'configs': names, 'members': 4, 'rounds': args.rounds,
              'production_noise_default': {'distribution': 'uniform', 'amplitude': .15},
              'fixture_noise': 'none; paired disclosure and pressure interface tests',
              'candidate_worlds': candidates, 'candidate_full_survival_fixed_seed_witnesses': successful,
              'lean_control_status': checked['status'], 'paid_model_calls': 0,
              'scope': 'Framework fixtures and candidate screening only. No model behavior results. Failed policy does not prove infeasibility. Noisy witnesses are not robust certificates.'}
    save(target/'index.json', result); save(reports/'summary.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('candidate_worlds',)}, ensure_ascii=False))


if __name__ == '__main__': main()
