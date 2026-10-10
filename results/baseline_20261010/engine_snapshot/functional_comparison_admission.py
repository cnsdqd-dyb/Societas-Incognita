"""Explicit runtime admission for the frozen 4-member, 50-round comparison.

This is not a Lean certificate. Other experiments retain the formal gate.
"""
import hashlib
import json
from pathlib import Path


def install(root):
    root = Path(root).resolve()
    import survival_certificates
    original = survival_certificates.validate_admission

    def validate(cfg):
        if cfg.get('experiment', {}).get('stage') != 'functional_homogeneous_4x50_runtime_comparison':
            return original(cfg)
        manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
        raw_config = (root / 'config.json').read_bytes()
        raw_witness = (root / 'runtime_survival_witness.json').read_bytes()
        if (cfg != json.loads(raw_config)
                or hashlib.sha256(raw_config).hexdigest() != manifest['config_sha256']
                or hashlib.sha256(raw_witness).hexdigest() != manifest['runtime_witness_sha256']):
            raise ValueError('Frozen configuration or runtime witness changed')
        expected = {'gptoss20b': ('openai/gpt-oss-20b', 'openrouter'),
                    'qwen7b': ('qwen/qwen-2.5-7b-instruct', 'openrouter'),
                    'luna_low': ('gpt-6-luna', 'codex_native_cli')}
        model, backend = expected[manifest['group']]
        if (cfg['models'] != [model] * 4 or cfg['rounds'] != 50
                or cfg['backend'] != backend or cfg['max_calls'] > 3000
                or cfg.get('require_end_to_end_world_proof')
                or cfg['experiment']['certificate_status'] != 'not_certified'):
            raise ValueError('Runtime comparison exceeds its explicit scope')
        for name, digest in manifest['frozen_engine_sha256'].items():
            if hashlib.sha256((root.parent / 'engine_snapshot' / name).read_bytes()).hexdigest() != digest:
                raise ValueError('Frozen engine changed: ' + name)
        witness = json.loads(raw_witness)
        if len(witness['plan']) != cfg['rounds']:
            raise ValueError('Witness horizon differs')
        import sim
        import environments
        from capability_feasibility import action_order
        society = sim.Society(cfg)
        for turn, joint in enumerate(witness['plan'], 1):
            if set(joint) != set(society.state['agents']):
                raise ValueError('Witness population differs')
            society.state['round'] = turn
            before = environments.physical_snapshot(society.state)
            for aid in action_order(cfg, turn, joint):
                society.act(aid, joint[aid])
            society.settle(before)
            if not all(a['alive'] for a in society.state['agents'].values()):
                raise ValueError('Runtime witness fails to preserve all members')
        return {'status': 'runtime_checked_not_lean_certified', 'rounds': 50, 'members': 4}

    survival_certificates.validate_admission = validate
