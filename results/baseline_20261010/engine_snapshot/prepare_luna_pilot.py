"""Prepare a bounded native Luna pipeline check; no external API credentials."""
import hashlib
import json
import shutil
from pathlib import Path

import certify_composed_worlds


def main():
    source = Path(__file__).resolve().parent
    root = source / 'runs/luna_low_pilot_20261010'
    if (root / 'config.json').exists():
        raise ValueError('Already prepared; resume with native_codex.py --run')
    root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((source / 'runs/mini_world_pilot_20261010/p1_hidden/config.json').read_text('utf-8'))
    for key in ('survival_certificate', 'campaign_budget_db', 'provider_only', 'planning_prices'):
        cfg.pop(key, None)
    cfg.update(models=['gpt-6-luna'] * 4, rounds=10, max_calls=180,
               backend='codex_native_cli', max_estimated_cost_usd=0)
    cfg['experiment'].update(stage='native_luna_low_bounded_pipeline_acceptance',
        purpose='Ten rounds check actions, communication, memory and resume; not an organization experiment',
        model='gpt-6-luna', reasoning_effort='low')
    plan = json.loads((source / 'runs/mini_world_pilot_20261010/p1_hidden/survival_certificate.json').read_text('utf-8'))['plan'][:10]
    path = root / 'survival_certificate.json'
    bundle = certify_composed_worlds.certify(cfg, plan, path, semantic=True)
    if bundle['lean']['status'] != 'lean_checked_composed_interval_certificate':
        raise ValueError('Luna pilot feasibility certificate failed')
    cfg['survival_certificate'] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (root / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    engine = root / 'engine_snapshot'
    engine.mkdir(exist_ok=True)
    hashes = {}
    for item in list(source.glob('*.py')) + list(source.glob('*.lean')):
        shutil.copy2(item, engine / item.name)
        hashes[item.name] = hashlib.sha256(item.read_bytes()).hexdigest()
    manifest = {'model': 'gpt-6-luna', 'reasoning_effort': 'low', 'members': 4,
                'rounds': 10, 'pressure': 1, 'rules': 'hidden', 'recipes': 'hidden',
                'native_call_cap': 180, 'external_api_calls': 0,
                'native_monetary_cost': None, 'frozen_engine_sha256': hashes}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'prepared': str(root), 'certificate': bundle['lean']['status']}), flush=True)


if __name__ == '__main__':
    main()
