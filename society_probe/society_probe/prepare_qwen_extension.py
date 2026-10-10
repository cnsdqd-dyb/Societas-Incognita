"""Freeze the fourth-model paired pilot without modifying completed runs."""
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from native_codex import write_json

ROOT = Path('runs/qwen7b_extension_20261009')
OLD = Path('runs/open_campaign_v1_20261007')
MODEL = 'qwen/qwen-2.5-7b-instruct'

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen('https://openrouter.ai/api/v1/models', timeout=30) as response:
        catalog = json.load(response)
    model = next(m for m in catalog['data'] if m['id'] == MODEL)
    assert {'response_format', 'structured_outputs'} <= set(model['supported_parameters'])
    write_json(ROOT / 'public_model_catalog.json', model)
    prior = json.loads((OLD / 'final_summary.json').read_text('utf-8'))['conservative_api_usd']
    cases = []
    for pressure in (True, False):
        name = 'qwen25_7b_p' + str(int(pressure))
        folder = ROOT / name
        folder.mkdir(exist_ok=True)
        source = OLD / ('ministral3b_p' + str(int(pressure)))
        cfg = json.loads((source / 'config.json').read_text('utf-8'))
        cfg['models'] = [MODEL] * 8
        cfg['max_estimated_cost_usd'] = 1.0
        for key in ('reasoning', 'provider_only', 'backend', 'native_effort'):
            cfg.pop(key, None)
        cfg['experiment']['extension'] = 'fourth_vendor_paired_pilot'
        if (folder / 'config.json').exists():
            assert json.loads((folder / 'config.json').read_text('utf-8')) == cfg
        else:
            write_json(folder / 'config.json', cfg)
            shutil.copytree(source / 'engine_snapshot', folder / 'engine_snapshot')
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder / 'engine_snapshot').glob('*.py')}
        write_json(folder / 'engine_hashes.json', hashes)
        cases.append({'name': name, 'model': MODEL, 'backend': 'openrouter', 'pressure': pressure, 'api_cost_cap_usd': 1.0})
    assert prior + sum(c['api_cost_cap_usd'] for c in cases) <= 5
    write_json(ROOT / 'manifest.json', {'runs': cases, 'additional_authorized_api_budget_usd': 5-prior,
        'original_additional_authorization_usd': 5, 'prior_closed_campaign_conservative_usd': prior,
        'allocated_api_caps_usd': 2, 'comparison_source': str(OLD), 'rounds': 50, 'agents': 8,
        'budget_note': 'Closed runs consume recorded conservative spend, not their unused historical caps.',
        'resume_command': 'python -X utf8 qwen_extension_runner.py --run runs/qwen7b_extension_20261009'})
    print(json.dumps({'model': MODEL, 'prior_conservative_usd': prior, 'new_caps_usd': 2, 'pricing': model['pricing']}))

if __name__ == '__main__':
    main()
