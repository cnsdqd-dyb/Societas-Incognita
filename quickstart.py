"""Offline demo by default; explicitly opt in to a bounded real-model pilot."""
import argparse
import copy
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'society_probe/society_probe'
sys.path.insert(0, str(SOURCE))


def witness(cfg):
    import sim
    import environments
    from capability_feasibility import action_order
    society = sim.Society(cfg); plan = []
    d = cfg['world']['mini_world']['definition']
    for turn in range(1, cfg['rounds'] + 1):
        society.state['round'] = turn
        before = environments.physical_snapshot(society.state); joint = {}
        for aid in action_order(cfg, turn, society.state['agents']):
            a = society.state['agents'][aid]
            candidates = [(q * d['resources'][k]['energy_value'], k, q)
                          for k, q in a['inventory'].items() if q > 0]
            if a['stock'] >= 8:
                action = {'tool': 'wait'}
            elif candidates:
                _, item, q = max(candidates)
                action = {'tool': 'liquidate', 'item': item,
                          'amount': min(2, q, d['resources'][item].get('liquidation_limit', 8))}
            else:
                item = max(society.state['mini_world']['pools'],
                    key=lambda k: society.state['mini_world']['pools'][k]*d['resources'][k]['energy_value'])
                action = {'tool': 'gather', 'item': item, 'amount': 2}
            society.act(aid, action); joint[aid] = action
        society.settle(before)
        if not all(a['alive'] for a in society.state['agents'].values()):
            raise ValueError('No all-member survival witness found by the demo planner; try fewer rounds or another seed. This does not prove the world infeasible.')
        plan.append(joint)
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['demo', 'openrouter', 'native'], default='demo')
    p.add_argument('--model', help='Explicit provider model identifier; required for real-model modes')
    p.add_argument('--rounds', type=int, default=8)
    p.add_argument('--seed', type=int, default=2)
    p.add_argument('--property-rules', action='store_true', help='Enable inferable property descriptions and limiting-reagent processing')
    p.add_argument('--api-cap', type=float, default=.25)
    p.add_argument('--output', default='output/quickstart')
    p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    if not 1 <= args.rounds <= 50: p.error('rounds must be in 1..50')
    if not math.isfinite(args.api_cap) or not 0 < args.api_cap <= 5: p.error('api-cap must be finite and in (0,5]')
    if args.mode != 'demo' and not args.model: p.error('Specify --model for a real-model pilot')
    if args.mode == 'native' and args.model not in ['gpt-6.1-sol', 'gpt-6-luna']:
        p.error('Native transport supports gpt-6.1-sol or gpt-6-luna, with low effort')
    if args.mode == 'openrouter' and not os.environ.get('OPENROUTER_API_KEY'):
        p.error('Set OPENROUTER_API_KEY in your environment; never commit it')
    out = Path(args.output).resolve()
    if args.resume:
        manifest = json.loads((out/'manifest.json').read_text('utf-8'))
        if args.mode != manifest['mode']: p.error('Resume with the original --mode')
        cfg = json.loads((out/'config.json').read_text('utf-8'))
        plan = json.loads((out/'runtime_witness.json').read_text('utf-8'))['plan']
        sys.path.insert(0, str(out/'engine_snapshot'))
    else:
        if out.exists(): p.error('Output exists; use --resume or choose another output directory')
        import world_rule_library as library
        import social_content
        source = json.loads((SOURCE/'configs/functional_services_20261010/native_base.json').read_text('utf-8'))
        candidate = library.with_capabilities(library.generate(args.seed, [k for k, _ in library.CANDIDATES_20]))
        if args.property_rules:
            candidate = library.with_property_rules(candidate)
        cfg = library.configure(source, candidate)
        cfg = social_content.configure(cfg)
        cfg['open_activities'] = {'version': 'open_activities_v1'}
        cfg['tools'] = sorted(set(cfg['tools']) | social_content.TOOLS | {'read_news', 'damage'})
        cfg.pop('survival_certificate', None)
        model = args.model or 'scripted-demo'
        backend = 'codex_native_cli' if args.mode == 'native' else 'openrouter'
        cfg.update(models=[model]*4, rounds=args.rounds, backend=backend, seed=7,
                   max_calls=3000, max_output_tokens=1600, max_estimated_cost_usd=args.api_cap if args.mode == 'openrouter' else 0,
                   survey_rounds=[], structured_outputs=True)
        cfg['model_routes'] = {model: {'backend': backend, 'parameters': {}}}
        cfg['experiment'].update(stage='public_quickstart_runtime_only', certificate_status='not_certified',
                                 population='scripted_demo' if args.mode == 'demo' else 'homogeneous_pilot',
                                 model_counts={model: 4})
        plan = witness(cfg)
        out.mkdir(parents=True)
        engine = out/'engine_snapshot'; engine.mkdir()
        for file in list(SOURCE.glob('*.py')) + list(SOURCE.glob('*.lean')):
            shutil.copy2(file, engine/file.name)
        (out/'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
        (out/'runtime_witness.json').write_text(json.dumps({'plan': plan, 'scope': 'One deterministic scripted survival path; not a Lean or discoverability proof'}, indent=2), 'utf-8')
        manifest = {'mode': args.mode, 'config_sha256': hashlib.sha256((out/'config.json').read_bytes()).hexdigest(),
            'witness_sha256': hashlib.sha256((out/'runtime_witness.json').read_bytes()).hexdigest(),
            'engine_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in engine.iterdir()}}
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2), 'utf-8')
    import sim
    import survival_certificates
    original = survival_certificates.validate_admission
    def admission(config):
        if config.get('experiment', {}).get('stage') != 'public_quickstart_runtime_only':
            return original(config)
        if config != cfg or hashlib.sha256((out/'config.json').read_bytes()).hexdigest() != manifest['config_sha256']:
            raise ValueError('Frozen quickstart configuration changed')
        if hashlib.sha256((out/'runtime_witness.json').read_bytes()).hexdigest() != manifest['witness_sha256']:
            raise ValueError('Runtime witness changed')
        for name, sha in manifest['engine_sha256'].items():
            if hashlib.sha256((out/'engine_snapshot'/name).read_bytes()).hexdigest() != sha:
                raise ValueError('Frozen quickstart engine changed')
        # Recheck in this process; the witness is independent of actor decisions.
        witness(config)
        return {'status': 'runtime_checked_not_lean_certified'}
    survival_certificates.validate_admission = admission
    if args.mode == 'demo':
        class ScriptedDemo(sim.API):
            def script(self, kind, payload):
                if kind == 'act':
                    return {'action': plan[payload['round']-1][payload['self']['id']], 'communication': {'op': 'silent'}}
                return super().script(kind, payload)
        sim.API = ScriptedDemo
    elif args.mode == 'native':
        from native_codex import NativeCodexAPI
        sim.API = NativeCodexAPI
    sim.run(cfg, out/'simulation', mock=args.mode == 'demo', resume=args.resume)
    print(f'Results: {out / "simulation/result.json"}')
    print('Demo decisions are scripted; real pilots are runtime-checked, not Lean certified.')


if __name__ == '__main__': main()
