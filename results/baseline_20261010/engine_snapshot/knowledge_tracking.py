"""Researcher-only claim checking. Never infers understanding from fluent text.

The first claim type predicts a station experiment's output in explicitly supplied
counterfactual states. Verification is scoped to those tests, not a universal proof.
Natural-language claim extraction and semantic transmission are separate work.
"""
import copy
import hashlib
import json

import mini_world


def knowledge_events(state):
    events = []
    for aid, a in state['agents'].items():
        for item, record in a.get('material_knowledge', {}).items():
            events.append({'round': record['first_round'], 'agent': aid,
                'kind': 'private_material_property_disclosure', 'item': item,
                'evidence': copy.deepcopy(record), 'knowledge_status': 'engine_disclosed_type_property_not_production_rule'})
    for aid, records in state.get('mini_world', {}).get('discoveries', {}).items():
        for record in records:
            events.append({'round': record['round'], 'agent': aid, 'kind': 'direct_experiment_observation',
                           'evidence': copy.deepcopy(record), 'knowledge_status': 'observation_not_verified_understanding'})
    for record in state.get('communication_events', []):
        if 'communication_error' in record['outcome']: continue
        msg = record['communication']
        if msg.get('op') in ('public', 'send'):
            events.append({'round': record['round'], 'agent': record['agent'], 'kind': 'message',
                           'channel': msg.get('chat', 'public'), 'text': msg.get('text', ''),
                           'knowledge_status': 'semantic_content_not_yet_verified'})
    return sorted(events, key=lambda e: (e['round'], e['agent'], e['kind']))


def verify_claim(cfg, claim, cases):
    if claim.get('type') != 'experiment_output' or not isinstance(cases, list) or not cases:
        raise ValueError('Provide an experiment-output claim and counterfactual cases')
    if not isinstance(claim.get('source'), dict) or not claim['source']:
        raise ValueError('Claims require provenance')
    experiment = copy.deepcopy(claim['action'])
    if experiment.get('tool') != 'experiment': raise ValueError('Expected experiment action')
    predicted = claim['predicted_output']; reports = []
    for case in cases:
        from sim import Society
        from environments import physical_snapshot
        c = copy.deepcopy(cfg); c['seed'] = case.get('seed', cfg['seed'])
        s = Society(c)
        if 'state' in case: s.state = copy.deepcopy(case['state'])
        s.state['round'] = case.get('round', s.state['round']+1)
        aid = case.get('agent', 'a0'); a = s.state['agents'][aid]
        # Counterfactual material endowment is supplied before anchoring the ledger.
        # It tests the rule, not feasibility of the claimant's original action.
        supplied = mini_world.parse_basket(c, experiment['inputs'])
        if 'ENERGY' in supplied: raise ValueError('Station inputs must be materials')
        a['inventory'].update({k: max(a['inventory'][k], amount*experiment['batches']) for k, amount in supplied.items()})
        # Keep liquid balances unchanged: world conditions may depend on them.
        ledger = s.state['mini_world']['ledger']; ledger.update(initial=mini_world.total_energy(c, s.state), external_input=0., dissipated=0., loss_by_cause={})
        before = physical_snapshot(s.state)
        s.act(aid, experiment); s.settle(before)
        result = s.state['mini_world']['discoveries'][aid][-1]['produced']
        prediction = case.get('predicted_output', predicted)
        if not isinstance(prediction, dict) or not set(prediction) <= set(mini_world.spec(c)['resources']):
            raise ValueError('Invalid output prediction')
        matched = all(abs(result.get(k, 0)-prediction.get(k, 0)) < 1e-9 for k in set(result) | set(prediction))
        reports.append({'case_id': case['id'], 'seed': c['seed'], 'actual': result,
                        'predicted': prediction, 'matched': matched})
    encoded = json.dumps(claim, sort_keys=True, ensure_ascii=False)
    return {'claim_id': hashlib.sha256(encoded.encode()).hexdigest(), 'claim': copy.deepcopy(claim),
            'status': 'passed_scoped_tests' if all(r['matched'] for r in reports) else 'refuted_in_tests',
            'tests': reports, 'world_sha256': __import__('world_rule_library').digest(mini_world.spec(cfg)),
            'scope': 'Exact output prediction on supplied cases, with material inputs endowed but liquid balances unchanged. Does not prove universal truth, agent understanding or causal benefit of transmission.'}
