"""Offline production/use differential checks; no language-model calls."""
import json
from pathlib import Path
import composed_certificates as proof
import world_rule_library as library


def main():
    output = Path('reports/twenty_mechanisms_20261010')
    rows = []
    keys = [key for key, _ in library.CANDIDATES_20]
    for selected in [[key] for key in keys] + [keys]:
        cfg = json.loads(Path('runs/sol_low_pilot_20261010/config.json').read_text('utf-8'))
        cfg.pop('survival_certificate', None)
        cfg['rounds'] = 3
        cfg['world']['mini_world']['definition'] = library.with_capabilities(library.generate(1, selected))['definition']
        import functional_effects
        cfg['tools'] = sorted(set(cfg['tools']) | {'use_function'} | functional_effects.STORAGE_TOOLS)
        d = cfg['world']['mini_world']['definition']
        d['initial_inventory'] = {item: 16 for item in d['resources']}
        recipe = d['recipes'][0]
        ids = ['a0', 'a1', 'a2', 'a3']
        plan = [{a: {'tool': 'wait'} for a in ids} for _ in range(3)]
        for a in ids[:2]:
            plan[0][a] = {'tool': 'experiment', 'facility': recipe['facility'],
                         'mode': recipe['mode'], 'inputs': [{'item': k, 'amount': v}
                         for k, v in recipe['inputs'].items()], 'batches': 1}
        plan[1]['a0'] = {'tool': 'use_item', 'item': 'D', 'amount': 1}
        plan[1]['a1'] = {'tool': 'use_item', 'item': 'C', 'amount': 1}
        name = selected[0] if len(selected) == 1 else 'all_twenty'
        artifact = proof.export(cfg, plan, output / f'{name}_active.lean', semantic=True)
        row = {'modules': selected, 'status': 'differential_checked_not_kernel_checked',
               'action_comparisons': artifact['action_phase_audit']['comparisons'],
               'round_comparisons': artifact['float_replay_audit']['comparisons']}
        # One full-composition active certificate additionally checks the kernel.
        if len(selected) > 1:
            checked = proof.check(artifact)
            row['status'] = checked['status']
            bundle = {'version': 'composed_semantic_survival_v2', 'plan': plan, 'lean': checked}
            (output / 'all_twenty_active.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
            (output / 'all_twenty_active_config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
            if row['status'] != 'lean_checked_composed_interval_certificate':
                raise RuntimeError(checked.get('diagnostics', row['status']))
        rows.append(row)
        (output / 'active_action_checks.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
