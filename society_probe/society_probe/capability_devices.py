"""Costly material assemblies; private, owned, bounded and next-round services.

No host code execution. Device recipes remain researcher-only. Stored device
energy counts once in the physical ledger; service fuel is dissipated.
"""
import copy
import hashlib
import random
import functional_effects

TOOLS = {'assemble_device', 'activate_device', 'give_device', 'dismantle_device',
         'write_note', 'read_note', 'measure'}
HELP = '''assemble_device(facility,mode,inputs) tries a material assembly; unmatched inputs are returned but the trial cost is spent.
activate_device(device,targets) pays fuel for each living recipient; service starts next physical round for a fixed duration.
give_device(device,target) transfers ownership and cancels all current service permissions.
dismantle_device(device) recovers its remaining embedded energy at the stated efficiency.
write_note(key,text) stores a private persistent record within your current character capacity; read_note(key) retrieves one.
measure(device,field) uses an authorized active device to measure a permitted state field with bounded error.
Material traits and device features are revealed to possessors, not by an offered promise or another member's claim.'''


def validate(d):
    import world_rule_engine as e
    recipes = d.get('device_recipes', [])
    if not isinstance(recipes, list) or len(recipes) > 64:
        raise ValueError('Invalid device recipes')
    signatures = set(); ids = set()
    for r in recipes:
        required = {'id', 'facility', 'mode', 'inputs', 'build_cost', 'retained_fraction',
                    'recovery_efficiency', 'fuel_per_recipient', 'duration', 'max_users', 'capabilities'}
        if not isinstance(r, dict) or set(r) != required:
            raise ValueError('Device recipe fields must be explicit')
        if not isinstance(r['id'], str) or not 0 < len(r['id']) <= 32 or r['id'] in ids:
            raise ValueError('Invalid device ID')
        ids.add(r['id'])
        if r['facility'] not in d['facilities'] or r['mode'] not in d['facilities'][r['facility']]['modes']:
            raise ValueError('Invalid device station')
        if not isinstance(r['inputs'], dict) or not r['inputs']:
            raise ValueError('Device needs material inputs')
        for k, n in r['inputs'].items():
            if k not in d['resources'] or type(n) is not int or not 1 <= n <= d['max_quantity']:
                raise ValueError('Invalid device inputs')
        sig = (r['facility'], r['mode'], tuple(sorted(r['inputs'].items())))
        if sig in signatures: raise ValueError('Ambiguous device assembly')
        signatures.add(sig)
        e.number(r['build_cost'], 0, 1e6)
        e.number(r['retained_fraction'], 0, 1)
        e.number(r['recovery_efficiency'], 0, 1)
        e.number(r['fuel_per_recipient'], 1e-6, 1e6)
        for key, maximum in (('duration', 100), ('max_users', 64)):
            if type(r[key]) is not int or not 1 <= r[key] <= maximum:
                raise ValueError('Invalid device service bound')
        cap = r['capabilities']
        if not isinstance(cap, dict) or not cap or not set(cap) <= {'communication_bonus', 'note_capacity', 'measurements', 'manufacturing'}:
            raise ValueError('Unknown device capability')
        for k in ('communication_bonus', 'note_capacity'):
            if k in cap and (type(cap[k]) is not int or not 1 <= cap[k] <= 100000):
                raise ValueError('Invalid device capacity')
        if 'manufacturing' in cap and cap['manufacturing'] is not True:
            raise ValueError('Invalid manufacturing capability')
        measurements = cap.get('measurements', {})
        if not isinstance(measurements, dict) or not set(measurements) <= set(d['variables']):
            raise ValueError('Unknown measurement field')
        for error in measurements.values(): e.number(error, 0, 1e6)
    for r in d['recipes']:
        if r.get('requires_capability') not in (None, 'manufacturing'):
            raise ValueError('Unknown production capability')
    base = d.get('note_base_capacity', 256)
    if type(base) is not int or not 0 <= base <= 100000:
        raise ValueError('Invalid base note capacity')


def initialize(state):
    state['mini_world'].update(devices={}, next_device=1)
    for a in state['agents'].values():
        a['private_notes'] = {}; a['device_knowledge'] = {}


def learn(state, aid, device):
    a = state['agents'][aid]; known = a.setdefault('device_knowledge', {})
    if device['id'] not in known:
        known[device['id']] = {'properties': copy.deepcopy(device['properties']),
            'first_round': state['round'], 'evidence': 'direct_possession'}
        a['inbox'].append({'round': state['round'], 'channel': 'device_property_disclosure', 'device': device['id']})


def service(device, round_number):
    pending = device.get('pending_service')
    return pending if pending and round_number >= pending['active_from'] else device


def active(state, aid):
    if not state['agents'][aid]['alive']: return []
    return [v for v in state['mini_world'].get('devices', {}).values()
            if functional_effects.device_factor(state, v) > 0
            and state['agents'][v['owner']]['alive'] and aid in service(v, state['round'])['users']
            and service(v, state['round'])['active_from'] <= state['round'] < service(v, state['round'])['active_until']]


def capacities(cfg, state, aid):
    d = cfg['world']['mini_world']['definition']
    devices = active(state, aid)
    return {'communication_bonus': min(100000, int(functional_effects.live_bonus(state, aid, 'communication_bonus') + sum(x['properties']['capabilities'].get('communication_bonus', 0) * functional_effects.device_factor(state, x) for x in devices))),
            'note_capacity': min(100000, int(d.get('note_base_capacity', 256) + functional_effects.agent_data(state, aid).get('note_bonus', 0) + sum(x['properties']['capabilities'].get('note_capacity', 0) * functional_effects.device_factor(state, x) for x in devices))),
            'manufacturing': any(x['properties']['capabilities'].get('manufacturing', False) for x in devices)}


def communication_limit(cfg, state, aid, base):
    # Bonus uses the configured character/token unit; a zero base explicitly disables communication.
    if base == 0 or 'budget' not in cfg.get('communication', {}): return base
    return min(100000, base+capacities(cfg, state, aid)['communication_bonus'])


def actor_device(device):
    return {k: copy.deepcopy(v) for k,v in device.items() if k != 'researcher_provenance'}


def observation(cfg, state, aid):
    return {'your_devices': {k: actor_device(v) for k, v in state['mini_world'].get('devices', {}).items() if v['owner'] == aid},
            'available_services': [{k: copy.deepcopy(v[k]) for k in ('id', 'owner', 'properties')} |
                {k: copy.deepcopy(service(v, state['round'])[k]) for k in ('active_from', 'active_until')}
                for v in active(state, aid)],
            'device_knowledge': copy.deepcopy(state['agents'][aid].get('device_knowledge', {})),
            'capabilities': capacities(cfg, state, aid),
            'private_note_index': {k: len(v) for k, v in state['agents'][aid].get('private_notes', {}).items()}}


def act(cfg, state, aid, action):
    import mini_world as w
    a = state['agents'][aid]; m = state['mini_world']; d = w.spec(cfg); tool = action['tool']
    if tool == 'assemble_device':
        if len(m['devices']) >= 128: raise ValueError('World device capacity reached; dismantle unused devices')
        facility, mode = action.get('facility'), action.get('mode')
        if facility not in d['facilities'] or mode not in d['facilities'][facility]['modes']:
            raise ValueError('Unknown station or mode')
        inputs = w.parse_basket(cfg, action.get('inputs'))
        if 'ENERGY' in inputs: raise ValueError('Assembly requires materials')
        w.check_payment(a, inputs); w.check_payment(a, {'ENERGY': d['experiment_cost']})
        a['stock'] -= d['experiment_cost']
        recipe = next((r for r in d.get('device_recipes', []) if r['facility'] == facility and r['mode'] == mode and r['inputs'] == inputs), None)
        if recipe is None: return {'assembled': False, 'trial_cost': d['experiment_cost']}
        w.check_payment(a, {'ENERGY': recipe['build_cost']})
        w.move(a, inputs, -1); a['stock'] -= recipe['build_cost']
        key = 'device'+str(m['next_device']); m['next_device'] += 1
        properties = {k: copy.deepcopy(recipe[k]) for k in ('recovery_efficiency', 'fuel_per_recipient', 'duration', 'max_users', 'capabilities')}
        device = {'id': key, 'owner': aid, 'properties': properties,
                  'embedded_energy': (w.basket_energy(cfg, inputs)+recipe['build_cost'])*recipe['retained_fraction'],
                  'users': [], 'active_from': 0, 'active_until': 0,
                  'researcher_provenance': {'recipe_id': recipe['id'], 'builder': aid,
                      'round': state['round'], 'inputs': copy.deepcopy(inputs), 'build_cost': recipe['build_cost']}}
        m['devices'][key] = device; learn(state, aid, device)
        return {'assembled': True, 'device': actor_device(device)}
    if tool in ('write_note', 'read_note'):
        key = action.get('key')
        if not isinstance(key, str) or not 0 < len(key) <= 64: raise ValueError('Invalid note key')
        notes = a['private_notes']; capacity = capacities(cfg, state, aid)['note_capacity']
        if tool == 'read_note':
            if key not in notes: raise ValueError('Unknown private note')
            if len(notes[key]) > capacity: raise ValueError('Active capacity too small to read this note')
            return {'key': key, 'text': notes[key]}
        text = action.get('text')
        if not isinstance(text, str) or sum(len(v) for k,v in notes.items() if k != key)+len(text) > capacity:
            raise ValueError('Private note capacity exceeded')
        notes[key] = text
        return {'key': key, 'stored_characters': len(text)}
    key = action.get('device'); device = m.get('devices', {}).get(key)
    if device is None: raise ValueError('Unknown device')
    p = device['properties']
    if tool == 'measure':
        field = action.get('field')
        if device not in active(state, aid) or field not in p['capabilities'].get('measurements', {}):
            raise ValueError('No active authorized measurement service')
        error = p['capabilities']['measurements'][field] / functional_effects.device_factor(state, device)
        seed = hashlib.sha256(f'{cfg["seed"]}:{state["round"]}:{aid}:{key}:{field}'.encode()).digest()
        import world_rule_engine as equations
        bias = equations.evaluate(w.spec(cfg).get('measurement_biases', {}).get(field, 0), w.context(cfg, state))
        value = m['variables'][field]+bias+random.Random(seed).uniform(-error, error)
        return {'field': field, 'measurement': value, 'absolute_error_bound': error+abs(bias), 'round': state['round']}
    if device['owner'] != aid: raise ValueError('Only the device owner can manage it')
    if tool == 'activate_device':
        users = action.get('targets')
        coverage = int(p['max_users'] * functional_effects.device_factor(state, device))
        if not isinstance(users, list) or not 1 <= len(users) <= coverage or len(set(users)) != len(users):
            raise ValueError('Invalid device recipients')
        for user in users:
            if user not in state['agents'] or not state['agents'][user]['alive']: raise ValueError('Inactive or unknown recipient')
        cost = p['fuel_per_recipient']*len(users); w.check_payment(a, {'ENERGY': cost}); a['stock'] -= cost
        # A renewal must not cancel the service already paid for in this round.
        current = copy.deepcopy(service(device, state['round']))
        for k in ('users', 'active_from', 'active_until'): device[k] = current[k]
        device['pending_service'] = {'users': users[:], 'active_from': state['round']+1,
                                     'active_until': state['round']+1+p['duration']}
        return {'device': key, 'fuel_paid': cost, **copy.deepcopy(device['pending_service'])}
    if tool == 'give_device':
        target = action.get('target'); w.target_agent(state, aid, target)
        device.update(owner=target, users=[], active_from=0, active_until=0); learn(state, target, device)
        device.pop('pending_service', None)
        return {'device': key, 'new_owner': target, 'service_cancelled': True}
    if tool == 'dismantle_device':
        recovered = device['embedded_energy']*p['recovery_efficiency']; a['stock'] += recovered
        del m['devices'][key]
        return {'device': key, 'recovered_energy': recovered}
    raise ValueError('Unknown device action')


def action_properties(cfg, tool):
    string = {'type': 'string'}
    if tool == 'assemble_device':
        import mini_world
        p = mini_world.action_properties(cfg, 'experiment'); p.pop('batches'); return p
    if tool == 'write_note': return {'key': {'type': 'string', 'maxLength': 64}, 'text': {'type': 'string', 'maxLength': 100000}}
    if tool == 'read_note': return {'key': {'type': 'string', 'maxLength': 64}}
    if tool == 'activate_device': return {'device': string, 'targets': {'type': 'array', 'items': string, 'minItems': 1, 'maxItems': 64, 'uniqueItems': True}}
    if tool == 'give_device': return {'device': string, 'target': string}
    if tool == 'measure': return {'device': string, 'field': string}
    return {'device': string}
