"""Freeze a small natural-inventory functional-world pilot; no model calls."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

from certify_twenty_mechanisms import greedy_survival
from sim import Society
import environments
from capability_feasibility import action_order


def main():
    source = Path(__file__).resolve().parent
    root = source/'runs/functional_sol_low_4x10_20261010'
    if root.exists(): raise ValueError('Run already exists; resume it rather than overwrite')
    cfg = json.loads((source/'reports/functional_services_20261010/world_config.json').read_text('utf-8'))
    cfg.update(rounds=10, max_calls=200, parallel_agents=4)
    cfg['experiment'].update(stage='small_functional_natural_inventory_pilot',
        purpose='Descriptive interface and exploration test, not a causal comparison or optimality result',
        certificate_status='not_certified', model='gpt-6.1-sol', reasoning_effort='low')
    # Check survival by a concrete runtime strategy in this exact configuration.
    # This is deliberately NOT labeled a Lean proof or a mathematical optimum.
    plan = greedy_survival(cfg)
    world = Society(cfg)
    for turn, joint in enumerate(plan, 1):
        world.state['round'] = turn
        before = environments.physical_snapshot(world.state)
        for aid in action_order(cfg, turn, joint): world.act(aid, joint[aid])
        world.settle(before)
    root.mkdir(parents=True)
    (root/'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    (root/'runtime_survival_witness.json').write_text(json.dumps({
        'scope': 'One deterministic runtime witness; no Lean proof, robustness or optimality claim',
        'plan': plan, 'final_alive': sum(a['alive'] for a in world.state['agents'].values()),
        'rounds': 10}, ensure_ascii=False, indent=2), 'utf-8')
    engine = root/'engine_snapshot'; engine.mkdir()
    hashes = {}
    for item in list(source.glob('*.py')) + list(source.glob('*.lean')):
        shutil.copy2(item, engine/item.name)
        hashes[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
    manifest = {'members': 4, 'rounds': 10, 'model': 'gpt-6.1-sol', 'effort': 'low',
        'generation_seed': cfg['experiment']['generation']['seed'], 'simulation_seed': cfg['seed'],
        'rules': 'hidden', 'recipes': 'hidden', 'pressure': True, 'advanced_inventory_gift': False,
        'service_types': cfg['experiment']['generation']['functional_services'],
        'native_call_cap': 200, 'external_api_calls': 0, 'native_cost_usd': None,
        'certificate_status': 'not_certified', 'runtime_survival_witness_alive': 4,
        'runtime_witness_sha256': hashlib.sha256((root/'runtime_survival_witness.json').read_bytes()).hexdigest(),
        'frozen_engine_sha256': hashes}
    (root/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'prepared': str(root), 'survival_witness_alive': 4, 'model_calls': 0}))


if __name__ == '__main__': main()
