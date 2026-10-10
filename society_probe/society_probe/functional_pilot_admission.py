"""Explicit runtime-only admission for a bounded diagnostic, never a Lean claim."""
import hashlib
import json
from pathlib import Path


def install(root):
    root = Path(root).resolve()
    import survival_certificates
    original = survival_certificates.validate_admission

    def validate(cfg):
        if cfg.get('experiment', {}).get('stage') != 'small_functional_natural_inventory_pilot':
            return original(cfg)
        if cfg.get('require_end_to_end_world_proof'):
            raise ValueError('Runtime diagnostic is not an end-to-end proof')
        if (cfg['rounds'] > 10 or len(cfg['models']) > 4 or cfg['max_calls'] > 200
                or cfg.get('backend') != 'codex_native_cli'
                or set(cfg['models']) != {'gpt-6.1-sol'}
                or cfg['experiment'].get('certificate_status') != 'not_certified'):
            raise ValueError('Runtime diagnostic exceeds its bounded scope')
        if cfg != json.loads((root/'config.json').read_text('utf-8')):
            raise ValueError('Diagnostic configuration changed')
        manifest = json.loads((root/'manifest.json').read_text('utf-8'))
        raw = (root/'runtime_survival_witness.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['runtime_witness_sha256']:
            raise ValueError('Diagnostic witness changed')
        witness = json.loads(raw)
        if len(witness['plan']) != cfg['rounds']:
            raise ValueError('Diagnostic witness horizon differs')
        import sim
        import environments
        from capability_feasibility import action_order
        society = sim.Society(cfg)
        for turn, joint in enumerate(witness['plan'], 1):
            if set(joint) != set(society.state['agents']):
                raise ValueError('Diagnostic witness population differs')
            society.state['round'] = turn
            before = environments.physical_snapshot(society.state)
            for aid in action_order(cfg, turn, joint): society.act(aid, joint[aid])
            society.settle(before)
            if not all(a['alive'] for a in society.state['agents'].values()):
                raise ValueError('Runtime witness does not preserve all members')
        return {'status': 'runtime_checked_diagnostic_not_lean_certified',
                'rounds': cfg['rounds'], 'members': len(cfg['models'])}

    survival_certificates.validate_admission = validate
