"""Fork settled checkpoints with matched state and explicit information changes."""
import copy
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def compatibility(cfg):
    # Match world, tools, models, random seed, memories and communication timing.
    return digest({k: cfg.get(k) for k in ('world', 'tools', 'models', 'seed', 'communication',
        'rescue', 'resource_seizure', 'social_content', 'open_activities', 'memory')})


def export_branch(cfg, settled_state, output, kind='control', verified_claims=None):
    if kind not in ('control', 'publish_verified_knowledge', 'placebo_message'):
        raise ValueError('Unsupported intervention')
    if settled_state['mini_world']['pending']:
        raise ValueError('Fork only settled checkpoints')
    state = copy.deepcopy(settled_state); claims = verified_claims or []
    if kind == 'publish_verified_knowledge':
        from world_rule_library import digest as world_digest
        if not claims or any(c['status'] != 'passed_scoped_tests' or c['world_sha256'] != world_digest(cfg['world']['mini_world']['definition']) for c in claims):
            raise ValueError('Publish only scoped-verified claims for this world')
        text = json.dumps([{'action': c['claim']['action'], 'predicted_output': c['claim']['predicted_output'],
                            'tested_cases': c['tests'], 'scope': c['scope']} for c in claims], ensure_ascii=False, sort_keys=True)
    else:
        text = 'No new production information is provided.' if kind == 'placebo_message' else None
    if text:
        for a in state['agents'].values():
            if a['alive']:
                a['inbox'].append({'round': state['round'], 'from': 'world_bulletin', 'channel': 'public',
                                   'text': text, 'evidence_type': 'published_scoped_test_results' if claims else 'neutral_notice'})
    provenance = {'kind': kind, 'source_state_sha256': digest(settled_state), 'source_round': settled_state['round'],
                  'claim_ids': [c['claim_id'] for c in claims],
                  'limitations': 'Relations, inventory and memory retained. Control/placebo is not automatically token-matched. Publishing text does not ensure equal understanding.'}
    document = {'version': 'mini_world_branch_v1', 'state': state, 'state_sha256': digest(state),
                'compatibility_sha256': compatibility(cfg), 'provenance': provenance}
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    from sim import dump
    dump(path, document)
    return document


def load_branch(cfg):
    branch = cfg['initial_checkpoint_branch']; path = Path(branch['path'])
    data = json.loads(path.read_text('utf-8'))
    if data.get('version') != 'mini_world_branch_v1' or digest(data) != branch['sha256']:
        raise ValueError('Branch document identity mismatch')
    if data['compatibility_sha256'] != compatibility(cfg) or data['state_sha256'] != digest(data['state']):
        raise ValueError('Branch state or physical configuration mismatch')
    if not 0 <= data['state']['round'] < cfg['rounds']:
        raise ValueError('Branch must precede target horizon')
    return copy.deepcopy(data['state'])
