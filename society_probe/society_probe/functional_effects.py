"""Executable artificial material services and destructive uses inside the world.

All state is checkpoint data. These effects never execute host code or create
physical energy; production improvements remain limited by reaction funding.
"""
import copy

KINDS = {
    'work_capacity': {'factor': 2}, 'note_capacity': {'amount': 1000},
    'communication_budget': {'amount': 500, 'duration': 3},
    'communication_range': {'amount': 2}, 'device_range': {'amount': 2},
    'measurement_precision': {'factor': .75}, 'diagnostics': {'amount': 1},
    'production_efficiency': {'factor': 1.15}, 'switch_speed': {'amount': 1},
    'storage_decay': {'factor': .85}, 'discharge_power': {'amount': 1},
    'rescue': {'restore_energy': 5}, 'fortify': {'amount': 1},
    'shield': {'amount': 1, 'duration': 3}, 'offer_duration': {'amount': 3},
    'device_corrosion': {'amount': .25}, 'repair_device': {'amount': .25},
    'device_interference': {'factor': .5, 'duration': 3},
    'pool_pollution': {'factor': .5, 'duration': 5}, 'purify': {'amount': 1},
    'facility_sabotage': {'duration': 2},
    'attack': {'vitality_loss': 2, 'stock_loss': 1},
    'area_attack': {'vitality_loss': 3, 'stock_loss': 2, 'duration': 3},
    'container_corrosion': {'factor': .15}}
STORAGE_TOOLS = {'store_item', 'withdraw_item', 'seize_storage'}
HELP = 'store_item(container,item,amount) stores owned material; withdraw_item(container,item,amount) withdraws owned material, including a final fractional residue. Containers retain ordinary material decay until upgraded. seize_storage(container,item,amount,effort) pays an attack fee and attempts fractional theft from another living owner; armor and defense reduce capture. All occupy one physical action.'


def enabled(cfg):
    return any(e['kind'] != 'world_state' for e in cfg['world']['mini_world']['definition'].get('combination_functions', []))


def validate(kind, parameters):
    import world_rule_engine as engine
    if kind not in KINDS or not isinstance(parameters, dict) or set(parameters) != set(KINDS[kind]):
        raise ValueError('Unimplemented effect or invalid effect parameters')
    for key, value in parameters.items():
        engine.number(value, 1e-6, 100000)
        if key in ('amount', 'duration', 'restore_energy', 'vitality_loss', 'stock_loss') and kind not in ('device_corrosion', 'repair_device'):
            if type(value) is not int:
                raise ValueError('Effect requires integer magnitude')
        if key == 'duration' and value > 100:
            raise ValueError('Effect duration exceeds bound')
        if key == 'restore_energy' and value > 5:
            raise ValueError('Invalid rescue vitality')
        if key == 'factor' and kind != 'work_capacity' and kind != 'production_efficiency' and value > 1:
            raise ValueError('Invalid attenuation factor')
        if key == 'factor' and kind in ('work_capacity', 'production_efficiency') and not 1 < value <= 4:
            raise ValueError('Invalid enhancement factor')


def initialize(cfg, state):
    if not enabled(cfg): return
    state['mini_world']['functional'] = {'agents': {}, 'facilities': {}, 'pools': {},
        'containers': {f'storage:{aid}': {'owner': aid, 'inventory': {}, 'decay_factor': 1.,
                                      'armor': 0., 'capacity': 64} for aid in state['agents']}}


def data(state):
    return state['mini_world'].get('functional', {})


def agent_data(state, aid):
    return data(state).get('agents', {}).get(aid, {})


def live_bonus(state, aid, key):
    a = agent_data(state, aid)
    return a.get(key, 0) if state['round'] < a.get(key + '_until', 0) else 0


def invite_limit(cfg, state, aid):
    return min(len(state['agents']) - 1, cfg['communication']['max_invitees'] + agent_data(state, aid).get('invite_bonus', 0))


def device_factor(state, device):
    factor = max(0., device.get('integrity', 1))
    if state['round'] < device.get('interference_until', 0):
        factor *= device.get('interference_factor', 1)
    return factor


def effective_definition(cfg, state):
    d = cfg['world']['mini_world']['definition']
    if not data(state): return d
    d = copy.deepcopy(d)
    for facility, upgrade in data(state)['facilities'].items():
        f = d['facilities'][facility]
        f['switch_rounds'] = max(0, f.get('switch_rounds', 0) - upgrade.get('switch_bonus', 0))
        if state['round'] < upgrade.get('blocked_until', 0): f['service_capacity'] = 0
        for recipe in d['recipes']:
            if recipe['facility'] == facility:
                recipe['yield'] = {'op': 'mul', 'args': [recipe['yield'], upgrade.get('yield_factor', 1)]}
    for item, effect in data(state)['pools'].items():
        if state['round'] < effect.get('until', 0):
            d['pools'][item]['regeneration'] = {'op': 'mul', 'args': [d['pools'][item]['regeneration'], effect['factor']]}
            d['pools'][item]['harvest_efficiency'] = {'op': 'mul', 'args': [d['pools'][item].get('harvest_efficiency', 1), effect['factor']]}
    return d


def liquidation_limit(cfg, state, aid, item):
    d = cfg['world']['mini_world']['definition']
    base = d['resources'][item].get('liquidation_limit', d['max_quantity'])
    return min(d['max_quantity'], base + agent_data(state, aid).get('discharge_bonus', 0))


def shared_left(state, aid):
    return sum(c.get('material_bonus_remaining', 0) for c in state['chats'].values()
               if c['open'] and aid in c['members'] and state['round'] < c.get('material_bonus_until', 0))


def spend_shared(state, aid, amount, chat):
    c = state['chats'].get(chat)
    if not c or not c['open'] or aid not in c['members'] or state['round'] >= c.get('material_bonus_until', 0): return 0
    spent = min(amount, c.get('material_bonus_remaining', 0))
    c['material_bonus_remaining'] -= spent
    return spent


def targets(cfg, state, aid, kind):
    f = data(state)
    devices = state['mini_world'].get('devices', {})
    if kind == 'world_state' or kind == 'area_attack': return ['world']
    if kind in ('note_capacity', 'communication_range', 'discharge_power', 'shield'): return [aid]
    if kind == 'communication_budget':
        if cfg.get('communication', {}).get('budget', {}).get('limit', 0) == 0: return []
        return [aid] + [key for key, c in state['chats'].items() if c['open'] and aid in c['members']]
    if kind == 'work_capacity':
        if not cfg.get('social_content'): return []
        import social_content
        return [key for key, w in social_content.repo(state)['artifacts'].items() if w['available'] and w['author'] == aid]
    if kind in ('device_range', 'measurement_precision', 'repair_device'):
        return [key for key, device in devices.items() if device['owner'] == aid and
                (kind != 'measurement_precision' or device['properties']['capabilities'].get('measurements'))]
    if kind in ('device_corrosion', 'device_interference'): return [key for key, device in devices.items() if device['owner'] != aid]
    if kind in ('diagnostics', 'production_efficiency', 'switch_speed', 'facility_sabotage'): return list(state['mini_world'].get('facility_schedulers', {})) or list(cfg['world']['mini_world']['definition']['facilities'])
    if kind in ('storage_decay', 'fortify'): return [key for key, c in f.get('containers', {}).items() if c['owner'] == aid]
    if kind == 'container_corrosion': return [key for key, c in f.get('containers', {}).items() if c['owner'] != aid]
    if kind in ('pool_pollution', 'purify'): return list(state['mini_world']['pools'])
    if kind == 'attack': return [key for key, a in state['agents'].items() if key != aid and a['alive']]
    if kind == 'rescue': return [key for key, a in state['agents'].items() if key != aid and not a['alive'] and a['energy'] == 0 and not a.get('pending_revival')]
    if kind == 'offer_duration':
        items = [key for key, o in state['mini_world']['offers'].items() if o['seller'] == aid and o['status'] == 'open' and o['expires'] > state['round']]
        items += [key for key, o in state.get('social_content', {}).get('offers', {}).items() if o['author'] == aid and o['status'] == 'open' and o['expires'] > state['round']]
        return items
    return []


def prepare(cfg, state, aid, entry, target):
    if target not in targets(cfg, state, aid, entry['kind']):
        raise ValueError('Function target is unavailable or unauthorized')


def apply(cfg, state, aid, entry, target):
    import mini_world as world
    kind, p = entry['kind'], entry['effects']
    f = data(state); t = state['round']
    personal = f['agents'].setdefault(aid, {})
    result = {'kind': kind, 'target': target}
    if kind == 'work_capacity':
        import social_content
        w = social_content.work(state, target)
        w['context_capacity'] = min(100000, int(w.get('context_capacity', cfg['social_content']['max_content_chars']) * p['factor']))
        result['context_capacity'] = w['context_capacity']
    elif kind in ('note_capacity', 'communication_range', 'discharge_power'):
        key = {'note_capacity': 'note_bonus', 'communication_range': 'invite_bonus', 'discharge_power': 'discharge_bonus'}[kind]
        personal[key] = min(100000, personal.get(key, 0) + p['amount'])
        result[key] = personal[key]
    elif kind in ('communication_budget', 'shield'):
        if kind == 'communication_budget' and target in state['chats']:
            c = state['chats'][target]
            c['material_bonus_remaining'] = min(100000, c.get('material_bonus_remaining', 0) + p['amount'])
            c['material_bonus_until'] = max(c.get('material_bonus_until', 0), t + p['duration'] + 1)
            result['shared_remaining'] = c['material_bonus_remaining']
        else:
            key = 'communication_bonus' if kind == 'communication_budget' else 'shield'
            personal[key] = min(100000, live_bonus(state, aid, key) + p['amount'])
            personal[key + '_until'] = t + p['duration'] + 1
            result['active_until'] = personal[key + '_until']
    elif kind in ('device_range', 'measurement_precision', 'repair_device', 'device_corrosion', 'device_interference'):
        device = state['mini_world']['devices'][target]
        props = device['properties']
        if kind == 'device_range': props['max_users'] = min(64, props['max_users'] + p['amount'])
        elif kind == 'measurement_precision':
            props['capabilities']['measurements'] = {k: n * p['factor'] for k, n in props['capabilities']['measurements'].items()}
        elif kind == 'device_interference':
            device.update(interference_factor=p['factor'], interference_until=t + p['duration'] + 1)
        else:
            device['integrity'] = min(1., max(0., device.get('integrity', 1) + p['amount'] * (1 if kind == 'repair_device' else -1)))
        owner = state['agents'][device['owner']]
        if target in owner.get('device_knowledge', {}): owner['device_knowledge'][target]['properties'] = copy.deepcopy(props)
        result['integrity'] = device.get('integrity', 1)
    elif kind in ('diagnostics', 'production_efficiency', 'switch_speed', 'facility_sabotage'):
        upgrade = f['facilities'].setdefault(target, {})
        if kind == 'production_efficiency': upgrade['yield_factor'] = min(4., upgrade.get('yield_factor', 1) * p['factor'])
        elif kind == 'facility_sabotage': upgrade['blocked_until'] = max(upgrade.get('blocked_until', 0), t + p['duration'] + 1)
        else:
            key = 'diagnostics' if kind == 'diagnostics' else 'switch_bonus'
            upgrade[key] = min(64, upgrade.get(key, 0) + p['amount'])
        result['upgrade'] = copy.deepcopy(upgrade)
    elif kind in ('storage_decay', 'fortify', 'container_corrosion'):
        container = f['containers'][target]
        if kind == 'storage_decay': container['decay_factor'] *= p['factor']
        elif kind == 'fortify': container['armor'] = min(100, container['armor'] + p['amount'])
        else:
            loss = p['factor'] / (1 + container['armor'])
            for item in container['inventory']: container['inventory'][item] *= 1 - loss
        result['decay_factor'] = container['decay_factor']; result['armor'] = container['armor']
    elif kind in ('pool_pollution', 'purify'):
        if kind == 'pool_pollution':
            old = f['pools'].get(target, {})
            current = old.get('factor', 1) if t < old.get('until', 0) else 1
            f['pools'][target] = {'factor': max(.01, current * p['factor']), 'until': t + p['duration'] + 1}
        else:
            old = f['pools'].get(target)
            if old:
                old['factor'] = min(1., old['factor'] * (2 ** p['amount']))
                if old['factor'] >= 1: f['pools'].pop(target, None)
    elif kind == 'offer_duration':
        o = state['mini_world']['offers'].get(target) or state.get('social_content', {}).get('offers', {}).get(target)
        o['expires'] += p['amount']
        result['expires'] = o['expires']
    elif kind == 'rescue':
        victim = state['agents'][target]
        victim['pending_revival'] = {'energy': p['restore_energy'], 'activate_round': t + 1, 'rescuer': aid}
        event = {'round': t, 'rescuer': aid, 'target': target, 'restore_energy': p['restore_energy'], 'activate_round': t + 1, 'source': entry['id']}
        state.setdefault('rescue_events', []).append(event); result.update(event)
    elif kind in ('attack', 'area_attack'):
        victims = targets(cfg, state, aid, 'attack') if kind == 'attack' else [key for key, a in state['agents'].items() if a['alive']]
        if kind == 'attack': victims = [target]
        injuries = {}
        for victim in victims:
            a = state['agents'][victim]
            defense = live_bonus(state, victim, 'shield')
            if cfg.get('resource_seizure', {}).get('version') == 'seizure_v2':
                import resource_seizure
                defense += resource_seizure.active_defense(state, victim)
            stock_loss = min(a['stock'], p['stock_loss'] / (1 + defense))
            vitality_loss = min(a['energy'], p['vitality_loss'] / (1 + defense))
            a['stock'] -= stock_loss; a['energy'] -= vitality_loss
            if a['energy'] <= 0:
                a['energy'] = 0; a['alive'] = False
                state['mini_world']['pending'].pop(victim, None)
            injuries[victim] = {'stock_loss': stock_loss, 'vitality_loss': vitality_loss, 'alive': a['alive']}
            a['inbox'].append({'round': t, 'channel': 'material_attack', 'from': aid, **injuries[victim]})
        if kind == 'area_attack':
            for item in state['mini_world']['pools']:
                f['pools'][item] = {'factor': .5, 'until': t + p['duration'] + 1}
            for facility in cfg['world']['mini_world']['definition']['facilities']:
                f['facilities'].setdefault(facility, {})['blocked_until'] = t + 2
            for device in state['mini_world'].get('devices', {}).values():
                device['integrity'] = max(0., device.get('integrity', 1) - .5)
            for container in f['containers'].values():
                for item in container['inventory']:
                    container['inventory'][item] *= 1 - .15 / (1 + container['armor'])
        result['injuries'] = injuries
    return result


def storage_action(cfg, state, aid, action):
    import mini_world as world
    f = data(state)
    container = f.get('containers', {}).get(action.get('container'))
    if not container: raise ValueError('Unknown material container')
    item = world.material(cfg, action.get('item'))
    amount = world.quantity(cfg, action.get('amount'))
    actor = state['agents'][aid]
    if action['tool'] == 'seize_storage':
        owner = container['owner']; victim = state['agents'][owner]
        if owner == aid or not victim['alive']: raise ValueError('Invalid container seizure target')
        effort = world.quantity(cfg, action.get('effort'), 2)
        fee = .5 * effort; world.check_payment(actor, {'ENERGY': fee})
        attack = world.spec(cfg)['resources'][item].get('accessibility', 1) * effort * (1 + actor['energy'] / 5)
        defense = (1 + victim['energy'] / 5) * (1 + container['armor'] + live_bonus(state, owner, 'shield'))
        if cfg.get('resource_seizure', {}).get('version') == 'seizure_v2':
            import resource_seizure
            defense += resource_seizure.active_defense(state, owner)
        taken = min(amount, container['inventory'].get(item, 0)) * attack / (attack + defense)
        world.move(actor, {'ENERGY': fee}, -1); world.move(actor, {item: taken}, 1)
        container['inventory'][item] = container['inventory'].get(item, 0) - taken
        victim['inbox'].append({'round': state['round'], 'channel': 'storage_seizure', 'from': aid, 'item': item, 'taken': taken})
        return world.event(state, aid, action['tool'], taken=taken, paid=fee, container=action['container'])
    if container['owner'] != aid: raise ValueError('Only container owner can store or withdraw')
    if action['tool'] == 'store_item':
        world.check_payment(actor, {item: amount})
        if sum(container['inventory'].values()) + amount > container['capacity']: raise ValueError('Container capacity exceeded')
        world.move(actor, {item: amount}, -1)
        container['inventory'][item] = container['inventory'].get(item, 0) + amount
    else:
        amount = min(amount, container['inventory'].get(item, 0))
        if amount <= 0: raise ValueError('Container material unavailable')
        container['inventory'][item] -= amount; world.move(actor, {item: amount}, 1)
    return world.event(state, aid, action['tool'], container=action['container'], item=item, amount=amount)


def observation(cfg, state, aid):
    f = data(state)
    if not f: return {}
    return {'your_storage': {key: copy.deepcopy(c) for key, c in f['containers'].items() if c['owner'] == aid},
            'storage_index': {key: {'owner': c['owner']} for key, c in f['containers'].items()},
            'personal_upgrades': copy.deepcopy(agent_data(state, aid)),
            'facility_upgrades': copy.deepcopy(f['facilities']),
            'pool_impairments': copy.deepcopy(f['pools'])}
