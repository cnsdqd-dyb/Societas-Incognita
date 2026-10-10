"""Add one non-thinking DeepSeek group without changing prior frozen engines."""
import hashlib
import json
import shutil
from pathlib import Path


def main():
    source = Path(__file__).resolve().parent
    reference = source / 'runs/functional_homogeneous_4x50_20261010'
    campaign = source / 'runs/functional_deepseek_flash_4x50_20261010'
    if campaign.exists():
        raise ValueError('DeepSeek group already exists; resume rather than overwrite')
    cfg = json.loads((reference / 'qwen7b/config.json').read_text('utf-8'))
    from shared_budget import SharedBudget
    budget = SharedBudget(cfg['campaign_budget_db']).status()
    if budget['cap_usd'] - budget['conservative_committed_usd'] < 1.5:
        raise ValueError('Existing authorized budget has insufficient headroom')
    model = 'deepseek/deepseek-v4.1-flash'
    cfg.update(models=[model]*4, max_estimated_cost_usd=1.5, structured_outputs=True)
    cfg['model_routes'] = {model: {'backend': 'openrouter', 'parameters': {
        'provider_only': ['InferenceNet'], 'reasoning': {'enabled': False}}}}
    # Conservative undiscounted price; actual response billing remains authoritative.
    cfg['planning_prices'] = {model: {'prompt': '0.00000007', 'completion': '0.0000006'}}
    cfg['experiment'].update(population='deepseek_flash', model=model, model_counts={model: 4},
        reasoning_effort='disabled', reasoning_enabled=False,
        model_revision='DeepSeek V4.1 Flash; explicit identifier, no latest alias',
        provider='InferenceNet', transport_protocol='strict json_schema; same contract as other external groups',
        comparison_note='Same physical world, observations, instructions, memory and dialogue allowance as the prior three groups; transport grammar enforcement differs.',
        reasoning_verification='Require disabled reasoning on every wire request; check reported reasoning tokens after replies.')
    campaign.mkdir()
    engine = campaign / 'engine_snapshot'
    shutil.copytree(reference / 'engine_snapshot', engine, ignore=shutil.ignore_patterns('__pycache__'))
    # Only the admission allowlist changes; the original three engines remain frozen.
    shutil.copy2(source / 'functional_comparison_admission.py', engine / 'functional_comparison_admission.py')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in list(engine.glob('*.py')) + list(engine.glob('*.lean'))}
    folder = campaign / 'deepseek_flash'
    folder.mkdir()
    (folder / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    shutil.copy2(reference / 'qwen7b/runtime_survival_witness.json', folder / 'runtime_survival_witness.json')
    old = json.loads((reference / 'qwen7b/manifest.json').read_text('utf-8'))
    manifest = {**old, 'group': 'deepseek_flash', 'model': model, 'backend': 'openrouter',
        'reasoning_enabled': False, 'provider': 'InferenceNet', 'external_cap_usd': 1.5,
        'config_sha256': hashlib.sha256((folder / 'config.json').read_bytes()).hexdigest(),
        'runtime_witness_sha256': hashlib.sha256((folder / 'runtime_survival_witness.json').read_bytes()).hexdigest(),
        'frozen_engine_sha256': hashes, 'matched_reference_campaign': str(reference)}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    (campaign / 'manifest.json').write_text(json.dumps({'stage': 'prepared', 'groups': [{
        'group': 'deepseek_flash', 'model': model, 'backend': 'openrouter', 'rounds': 50,
        'members': 4, 'external_cap_usd': 1.5}], 'runtime_only': True,
        'reasoning_enabled': False, 'world_rules_unchanged': cfg['world'] == json.loads(
            (reference / 'qwen7b/config.json').read_text('utf-8'))['world'],
        'existing_budget_status': budget, 'model_calls_in_preparation': 0}, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'prepared': str(folder), 'model': model, 'reasoning': False,
        'api_cap_usd': 1.5, 'prior_engines_unchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
