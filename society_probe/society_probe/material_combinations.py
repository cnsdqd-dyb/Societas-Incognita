"""Private combination discoveries; explicitly confirmed bounded world effects."""
import copy
import functional_effects

TOOL = 'use_function'
HELP = 'use_function(function,target,confirm): select a function from your private panel. confirm=true pays its costs and executes; confirm=false cancels without payment. Both occupy one physical action slot.'


def validate(d):
    import world_rule_engine as engine
    entries = d.get('combination_functions', [])
    if not isinstance(entries, list) or len(entries) > 64:
        raise ValueError('Invalid combination functions')
    seen = set()
    for e in entries:
        if not isinstance(e, dict) or set(e) != {'id', 'name', 'requires', 'consume', 'energy_cost', 'kind', 'effects'}:
            raise ValueError('Invalid combination contract')
        if not isinstance(e['id'], str) or not 0 < len(e['id']) <= 64 or e['id'] in seen:
            raise ValueError('Invalid combination ID')
        seen.add(e['id'])
        if not isinstance(e['name'], str) or not 0 < len(e['name']) <= 180:
            raise ValueError('Invalid combination name')
        if not isinstance(e['requires'], dict) or not 1 <= len(e['requires']) <= len(d['resources']):
            raise ValueError('Function needs material requirements')
        if not isinstance(e['consume'], dict) or not e['consume'] or not set(e['consume']) <= set(e['requires']):
            raise ValueError('Invalid combination payment')
        for item, quantity in e['requires'].items():
            if item not in d['resources']:
                raise ValueError('Unknown combination material')
            engine.number(quantity, 1e-6, 1e6)
        for item, quantity in e['consume'].items():
            engine.number(quantity, 1e-6, e['requires'][item])
        engine.number(e['energy_cost'], 0, 1e6)
        if e['kind'] != 'world_state':
            functional_effects.validate(e['kind'], e['effects'])
        else:
            if not isinstance(e['effects'], dict) or not e['effects'] or not set(e['effects']) <= set(d['variables']):
                raise ValueError('Unknown combination effect target')
            for effect in e['effects'].values():
                engine.validate_expression(effect, engine.references(d))


def synchronize(cfg, state, source):
    entries = cfg['world']['mini_world']['definition'].get('combination_functions', [])
    if not entries:
        return
    for aid, a in state['agents'].items():
        known = a.setdefault('function_knowledge', {})
        for e in entries:
            if e['id'] in known or not all(a['inventory'].get(k, 0) >= n for k, n in e['requires'].items()):
                continue
            known[e['id']] = {'properties': copy.deepcopy(e), 'first_round': state['round'],
                              'source': source, 'evidence': 'direct_combination_possession'}
            a['inbox'].append({'round': state['round'], 'channel': 'combination_function_disclosure',
                               'function': e['id'], 'source': source})


def observation(cfg, state, aid):
    a = state['agents'][aid]
    panel = {}
    for key, knowledge in a.get('function_knowledge', {}).items():
        e = knowledge['properties']
        missing = {k: n - a['inventory'].get(k, 0) for k, n in e['requires'].items() if a['inventory'].get(k, 0) < n}
        energy_missing = max(0, e['energy_cost'] - a['stock'])
        targets = functional_effects.targets(cfg, state, aid, e['kind'])
        panel[key] = {**copy.deepcopy(knowledge), 'available': a['alive'] and not missing and energy_missing == 0 and bool(targets),
                      'missing_materials': missing, 'missing_energy': energy_missing,
                      'interface': {'tool': TOOL, 'function': key, 'allowed_targets': targets,
                                    'confirm': 'true executes; false cancels', 'physical_action_slots': 1}}
    return panel


def act(cfg, state, aid, action):
    import mini_world
    a = state['agents'][aid]
    key = action.get('function')
    if not isinstance(key, str) or key not in a.get('function_knowledge', {}):
        raise ValueError('Function has not been privately discovered')
    if type(action.get('confirm')) is not bool:
        raise ValueError('Invalid function confirmation or target')
    if not action['confirm']:
        return mini_world.event(state, aid, TOOL, function=key, cancelled=True, paid=False)
    if not isinstance(action.get('target'), str):
        raise ValueError('Confirmed function needs a target')
    e = a['function_knowledge'][key]['properties']
    if e['kind'] != 'world_state':
        functional_effects.prepare(cfg, state, aid, e, action['target'])
    elif action['target'] != 'world':
        raise ValueError('Invalid world-state target')
    # Exact possession threshold also used by discovery and availability.
    if not all(a['inventory'].get(k, 0) >= n for k, n in e['requires'].items()):
        raise ValueError('Combination materials are missing')
    mini_world.check_payment(a, {'ENERGY': e['energy_cost']})
    d = mini_world.spec(cfg)
    context = mini_world.context(cfg, state)
    changes = {k: mini_world.equations.evaluate(effect, context) for k, effect in e['effects'].items()} if e['kind'] == 'world_state' else {}
    mini_world.move(a, e['consume'], -1)
    mini_world.move(a, {'ENERGY': e['energy_cost']}, -1)
    for item, amount in e['consume'].items():
        mini_world.add_activity(state, 'consumed', item, amount)
    for field, delta in changes.items():
        bound = d['variables'][field]
        state['mini_world']['variables'][field] = min(bound['max'], max(bound['min'], state['mini_world']['variables'][field] + delta))
    outcome = functional_effects.apply(cfg, state, aid, e, action['target']) if e['kind'] != 'world_state' else {}
    return mini_world.event(state, aid, TOOL, function=key, cancelled=False, paid=True, outcome=outcome,
                            consumed=copy.deepcopy(e['consume']), energy_paid=e['energy_cost'],
                            observable_state={k: state['mini_world']['variables'][k] for k in changes if d['variables'][k].get('observable', True)})


def action_properties():
    return {'function': {'type': 'string', 'minLength': 1, 'maxLength': 64},
            'target': {'type': ['string', 'null'], 'minLength': 1, 'maxLength': 128}, 'confirm': {'type': 'boolean'}}
