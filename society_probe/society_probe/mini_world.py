"""Conserved material economy and state-dependent hidden production graph.

Agent stock is liquid energy; agent energy is the existing 0..5 vitality score,
not another physical energy store. Researchers see recipes and accounting;
actor views contain only the chosen rule disclosure and observable feedback.
"""
import copy
import hashlib
import json
import math
import random

import world_rule_engine as equations
import material_knowledge
import capability_devices
import material_combinations
import functional_effects
from interface_feedback import InterfaceError, experiment_feedback

TOOLS = {'wait', 'inspect', 'transfer', 'gather', 'experiment', 'liquidate',
         'use_item', 'give_item', 'offer_items', 'accept_items', 'cancel_items', 'seize_item'}
TOOLS |= capability_devices.TOOLS
TOOLS.add(material_combinations.TOOL)
TOOLS |= functional_effects.STORAGE_TOOLS
HELP = '''One physical action per round. ENERGY denotes liquid stock; self.energy is vitality.
gather(item,amount): attempt to extract a visible pool material.
experiment(facility,mode,inputs:[{item,amount}],batches): attempt a combination at a station.
Each material appears once in a basket; combine repeated quantities into one entry and check the visible quantity limit. Inputs must come from your own available inventory. Decimal quantities are allowed when the interface declares them; batches are integers.
Inputs list names one-batch quantities; batches multiplies them. Results arrive at settlement.
In continuous worlds material/ENERGY amounts may be positive decimals; batches and attack effort remain integers.
liquidate(item,amount): attempt to convert a held material into liquid energy.
use_item(item,amount): consume a material to apply its world-state function, if it has one.
give_item(target,item,amount,note): transfer a held material (or ENERGY); note records a voluntary purpose such as custody.
offer_items(target,give:[{item,amount}],want:[{item,amount}]): escrow your give basket; target is an existing living ID or public. ENERGY can be traded.
accept_items(offer): exchange the escrowed basket atomically if you can pay; cancel_items(offer): creator refunds their offer.
seize_item(target,item,amount,effort): attempt material seizure; existing defend prepares next-round defense.
wait does nothing; inspect reveals public member balances. transfer(target,amount) transfers liquid ENERGY.
Tool syntax specifies operations, not goals. Knowledge claims and custody promises are not guaranteed by the engine.'''
HELP += '\n'+capability_devices.HELP
HELP += '\n'+material_combinations.HELP
HELP += '\n'+functional_effects.HELP


def enabled(cfg):
    return cfg['world'].get('mechanism') == 'mini_world'


def spec(cfg):
    return equations.definition(cfg)


def initialize(cfg, state):
    d = equations.validate(spec(cfg))
    if d.get('combination_functions') and material_combinations.TOOL not in cfg['tools']:
        raise ValueError('Combination functions require the use_function tool')
    if cfg.get('recipe_visibility', 'hidden') not in ('hidden', 'full'):
        raise ValueError('recipe_visibility must be hidden or full')
    if cfg.get('mixed_world') or cfg.get('open_contest'):
        raise ValueError('Mini-world replaces legacy mixed physical dynamics')
    if 'seize_item' in cfg['tools'] and cfg.get('resource_seizure', {}).get('version') != 'seizure_v2':
        raise ValueError('Material seizure requires seizure_v2 defense')
    state['mini_world'] = {
        'variables': {k: v['initial'] for k, v in d['variables'].items()},
        'pools': {k: p['initial'] for k, p in d['pools'].items()},
        'reserve': d['initial_reserve'], 'pending': {}, 'activity': {},
        'offers': {}, 'next_offer': 1, 'events': [], 'discoveries': {},
        'ledger': {'initial': 0., 'external_input': 0., 'dissipated': 0., 'loss_by_cause': {}}}
    state['zones'] = []
    for a in state['agents'].values():
        a['inventory'] = {k: float(d.get('initial_inventory', {}).get(k, 0)) for k in d['resources']}
        a['material_knowledge'] = {}
    capability_devices.initialize(state)
    functional_effects.initialize(cfg, state)
    material_knowledge.synchronize(cfg, state, 'initial_inventory')
    material_combinations.synchronize(cfg, state, 'initial_inventory')
    state['mini_world']['ledger']['initial'] = total_energy(cfg, state)


def basket_energy(cfg, basket):
    return sum(amount*(1 if k == 'ENERGY' else spec(cfg)['resources'][k]['energy_value'])
               for k, amount in basket.items())


def total_energy(cfg, state):
    m = state['mini_world']
    total = m['reserve'] + basket_energy(cfg, m['pools'])
    total += sum(a['stock']+a.get('vault', 0)+basket_energy(cfg, a['inventory']) for a in state['agents'].values())
    total += sum(basket_energy(cfg, p['inputs'])+p['energy_paid'] for p in m['pending'].values())
    total += sum(basket_energy(cfg, o['give']) for o in m['offers'].values() if o['status'] == 'open')
    total += sum(sum(g['escrow'].values()) for g in state.get('social_content', {}).get('games', {}).values())
    total += sum(v['embedded_energy'] for v in m.get('devices', {}).values())
    total += sum(basket_energy(cfg, c['inventory']) for c in functional_effects.data(state).get('containers', {}).values())
    return total


def account_loss(cfg, state, before, cause, external=0.):
    m = state['mini_world']; loss = before+external-total_energy(cfg, state)
    if loss < -1e-7*max(1, before+external):
        raise ValueError('Unaccounted energy creation')
    loss = max(0., loss); ledger = m['ledger']
    ledger['external_input'] += external; ledger['dissipated'] += loss
    ledger['loss_by_cause'][cause] = ledger['loss_by_cause'].get(cause, 0)+loss
    return loss


def accounting(cfg, state):
    l = state['mini_world']['ledger']; retained = total_energy(cfg, state)
    expected = l['initial']+l['external_input']-l['dissipated']
    residual = expected-retained
    if abs(residual) > 1e-7*max(1, l['initial']+l['external_input']):
        raise ValueError('Mini-world conservation ledger does not balance')
    return {**copy.deepcopy(l), 'retained': retained, 'residual': residual,
            'scope': 'Physical energy equivalent incl. environment reserve, material pools, dead inventories, vaults, material containers, embedded device energy, production escrow, item-offer escrow and game escrow. Vitality is excluded.'}


def context(cfg, state):
    m = state['mini_world']
    c = {'round': state['round'], 'living': sum(a['alive'] for a in state['agents'].values()),
         'liquid_total': sum(a['stock'] for a in state['agents'].values())}
    c.update({'state.'+k: v for k, v in m['variables'].items()})
    c.update({'pool.'+k: v for k, v in m['pools'].items()})
    for name in ('produced', 'harvested', 'consumed'):
        for k in spec(cfg)['resources']:
            c['activity.'+name+'.'+k] = m['activity'].get(name, {}).get(k, 0)
    for k in spec(cfg)['facilities']:
        c['activity.submitted.'+k] = m['activity'].get('submitted', {}).get(k, 0)
    return c


def add_activity(state, name, item, amount):
    activity = state['mini_world']['activity'].setdefault(name, {})
    activity[item] = activity.get(item, 0)+amount


def noise(cfg, state, aid, channel):
    n = spec(cfg)['noise']; width = n['amplitude']
    rng = random.Random(f"{cfg['seed']}:{state['round']}:{aid}:{channel}:mini-v1")
    if n['distribution'] == 'none': return 1.
    if n['distribution'] == 'uniform': return rng.uniform(1-width, 1+width)
    return rng.triangular(1-width, 1+width, 1)


def snapshot(state):
    return copy.deepcopy({k: state['mini_world'][k] for k in ('variables', 'pools', 'reserve', 'activity')})


def observation(cfg, state, aid):
    d = spec(cfg); m = state['mini_world']; a = state['agents'][aid]
    from identity_names import display_name
    catalog = [{'item': k, 'name': display_name(cfg,'materials',k,r.get('name',k))} for k, r in d['resources'].items()]
    offers = {k: copy.deepcopy(o) | {'remaining_rounds': max(0, o['expires']-state['round'])}
              for k, o in m['offers'].items() if o['status'] == 'open' and o['expires'] > state['round']
              and (o['target'] in (aid, 'public') or o['seller'] == aid)}
    result = {'family': 'mini_world', 'material_catalog': catalog,
              'your_inventory': copy.deepcopy(a['inventory']), 'material_pools': copy.deepcopy(m['pools']),
              'world_state': {k: v for k, v in m['variables'].items() if d['variables'][k].get('observable', True)},
              'stations': [{'facility': k, 'name': f.get('name', k), 'modes': list(f['modes'])} for k, f in d['facilities'].items()],
              'pending_experiment': aid in m['pending'], 'item_offers': offers,
              'your_experiment_records': copy.deepcopy(m['discoveries'].get(aid, [])[-6:]),
              'physical_semantics': 'stock is liquid energy; energy is vitality. Material and ENERGY transfers change ownership, not total energy. Inactive inventories persist.',
              'production_semantics': d.get('production_semantics','exact_integer_v1'),
              'interface_limits': {k: d[k] for k in ('max_quantity', 'max_batches', 'offer_ttl')},
              'recent_item_notices': [copy.deepcopy(e) for e in m['events'][-32:] if e.get('agent') == aid or e.get('target') == aid][-6:]}
    if cfg.get('recipe_visibility', 'hidden') == 'full':
        result['production_rules'] = copy.deepcopy(d['recipes'])
    if d.get('production_semantics') == 'proportional_v1':
        result['processing_interface'] = 'Recipes accept scaled matching ratios, including decimal input amounts. Fractional products accumulate and may be processed, transferred or liquidated. Batches remain positive integers. Ordinary decay and explicitly declared station minimums apply.'
        for station in result['stations']:
            minimum = d['facilities'][station['facility']].get('min_processing_extent')
            if minimum is not None: station['min_processing_extent'] = minimum
    result['your_material_knowledge'] = material_knowledge.observe(state, aid)
    result.update(capability_devices.observation(cfg, state, aid))
    result.update(functional_effects.observation(cfg, state, aid))
    if d.get('combination_functions'):
        result['your_functions'] = material_combinations.observation(cfg, state, aid)
    import property_rules
    result = property_rules.observe(d, state, result)
    return result


def public_rules(cfg):
    d = copy.deepcopy(spec(cfg))
    d['resources'] = {k: {'name': r.get('name', k)} for k, r in d['resources'].items()}
    d.pop('device_recipes', None)
    d.pop('combination_functions', None)
    if cfg.get('recipe_visibility', 'hidden') != 'full': d.pop('recipes', None)
    return {'mechanism': 'mini_world', 'survival_pressure': cfg['world']['survival_pressure'],
            'consumption': cfg['world']['consumption'], 'definition': d,
            'recipe_visibility': cfg.get('recipe_visibility', 'hidden'),
            'maintenance_rule': 'Physical outputs settle before maintenance. Under pressure, full liquid-energy consumption restores one vitality up to five; shortage loses one. Zero vitality is inactive. Rescue, when enabled, is paid by another member and activates next round.'}


def continuous_quantities(cfg):
    d = spec(cfg)
    import production_semantics
    return d.get('quantity_semantics') == 'continuous_v1' or production_semantics.proportional(d)


def quantity(cfg, value, maximum=None, integer=False):
    cap = spec(cfg)['max_quantity'] if maximum is None else maximum
    if integer or not continuous_quantities(cfg):
        if type(value) is not int or not 1 <= value <= cap:
            raise InterfaceError('Invalid integer quantity','INTEGER_QUANTITY','amount/batches',
                '此数量须为允许范围内的正整数。','按接口范围提交整数；不能提交小数、字符串或布尔值。',{'maximum':cap,'integer_required':True})
    elif type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= cap:
        raise InterfaceError('Invalid finite positive quantity','POSITIVE_QUANTITY','amount',
            '数量须为允许范围内的有限正数。','允许小数，但不能为0、负数、NaN、无穷、字符串或布尔值。',{'maximum':cap,'decimal_allowed':True})
    return value


def material(cfg, item, allow_energy=False):
    if item not in spec(cfg)['resources'] and not (allow_energy and item == 'ENERGY'):
        raise ValueError('Unknown material')
    return item


def parse_basket(cfg, value):
    if not isinstance(value, list) or not 1 <= len(value) <= len(spec(cfg)['resources'])+1:
        raise ValueError('Invalid basket')
    basket = {}
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {'item', 'amount'}: raise ValueError('Invalid basket entry')
        k = material(cfg, entry['item'], True)
        if k in basket:
            raise InterfaceError('Duplicate basket material','DUPLICATE_MATERIAL','inputs',
                '材料 '+k+' 在同一清单中重复出现。','同种材料须合并成一项；例如8A和2A写为 {"item":"A","amount":10}，再核对数量上限和自己的库存。',{'item':k})
        basket[k] = quantity(cfg, entry['amount'])
    return basket


def balance(a, item):
    return a['stock'] if item == 'ENERGY' else a['inventory'][item]


def check_payment(a, basket):
    shortages=[{'item':k,'required':amount,'available':balance(a,k),'shortfall':amount-balance(a,k)}
               for k,amount in basket.items() if balance(a,k)<amount]
    if shortages:
        raise InterfaceError('Insufficient assets','INSUFFICIENT_ASSETS','amount/inputs',
            '自己的可用资产不足以支付本次操作。','将数量降至实际可用余额以内，或先取得所需资源；余额有小数，不能向上取整。',{'shortages':shortages})


def move(a, basket, sign):
    for k, amount in basket.items():
        if k == 'ENERGY': a['stock'] = max(0., a['stock']+sign*amount)
        else: a['inventory'][k] = max(0., a['inventory'][k]+sign*amount)


def target_agent(state, aid, target):
    if target == aid or target not in state['agents'] or not state['agents'][target]['alive']:
        raise ValueError('Recipient must be another living member')
    return state['agents'][target]


def event(state, aid, tool, **fields):
    e = {'round': state['round'], 'agent': aid, 'tool': tool, **fields}
    state['mini_world']['events'].append(e)
    return copy.deepcopy(fields)


def act(cfg, state, aid, action):
    d = spec(cfg); m = state['mini_world']; a = state['agents'][aid]; tool = action.get('tool')
    if tool not in cfg['tools'] or not a['alive']: raise ValueError('Unavailable material action')
    if tool == material_combinations.TOOL:
        return material_combinations.act(cfg, state, aid, action)
    if tool in functional_effects.STORAGE_TOOLS:
        return functional_effects.storage_action(cfg, state, aid, action)
    if tool in capability_devices.TOOLS:
        outcome = capability_devices.act(cfg, state, aid, action)
        event(state, aid, tool, **outcome)
        return outcome
    if tool == 'wait': return {'waited': True}
    if tool == 'inspect':
        return {'balances': {k: {'stock': v['stock'], 'inventory': copy.deepcopy(v['inventory']),
                               'energy': v['energy'], 'alive': v['alive']} for k, v in state['agents'].items()}}
    if tool == 'transfer':
        target = target_agent(state, aid, action.get('target')); amount = quantity(cfg, action.get('amount'))
        check_payment(a, {'ENERGY': amount}); move(a, {'ENERGY': amount}, -1); move(target, {'ENERGY': amount}, 1)
        return event(state, aid, tool, target=action['target'], transferred=amount)
    if tool == 'experiment':
        if aid in m['pending']: raise ValueError('Already has a pending experiment')
        facility = action.get('facility'); mode = action.get('mode')
        if facility not in d['facilities'] or mode not in d['facilities'][facility]['modes']:
            raise ValueError('Unknown station or mode')
        batches = quantity(cfg, action.get('batches'), d['max_batches'], integer=True)
        inputs = parse_basket(cfg, action.get('inputs'))
        if 'ENERGY' in inputs: raise ValueError('Use material inputs at stations')
        inputs = {k: amount*batches for k, amount in inputs.items()}
        check_payment(a, inputs)
        if a['stock']+1e-9 < d['experiment_cost']: raise ValueError('Cannot pay experiment operation cost')
        move(a, inputs, -1); a['stock'] = max(0., a['stock']-d['experiment_cost'])
        m['pending'][aid] = {'facility': facility, 'mode': mode, 'inputs': inputs, 'batches': batches, 'energy_paid': 0.}
        if any('service_capacity' in f for f in d['facilities'].values()) or functional_effects.enabled(cfg):
            m['pending'][aid].update(submitted_round=state['round'], nominal_inputs=copy.deepcopy(inputs))
        add_activity(state, 'submitted', facility, 1)
        return {'experiment_queued': True, 'inputs_reserved': inputs}
    if tool == 'offer_items':
        target = action.get('target')
        if target != 'public': target_agent(state, aid, target)
        give = parse_basket(cfg, action.get('give')); want = parse_basket(cfg, action.get('want'))
        check_payment(a, give)
        if sum(o['status'] == 'open' for o in m['offers'].values()) >= d['max_offers']:
            raise ValueError('Item offer capacity reached')
        key = 'item_offer'+str(m['next_offer']); m['next_offer'] += 1; move(a, give, -1)
        m['offers'][key] = {'seller': aid, 'target': target, 'give': give, 'want': want,
                           'expires': state['round']+d['offer_ttl'], 'status': 'open'}
        return event(state, aid, tool, offer=key, target=target, give=give, want=want)
    if tool in ('accept_items', 'cancel_items'):
        key = action.get('offer'); offer = m['offers'].get(key)
        if not offer or offer['status'] != 'open' or offer['expires'] <= state['round']:
            raise ValueError('Item offer unavailable')
        seller = state['agents'][offer['seller']]
        if tool == 'cancel_items':
            if offer['seller'] != aid: raise ValueError('Only seller can cancel')
            move(seller, offer['give'], 1); offer['status'] = 'cancelled'
            return event(state, aid, tool, offer=key)
        if not seller['alive'] or offer['seller'] == aid or offer['target'] not in (aid, 'public'):
            raise ValueError('Not eligible to accept offer')
        check_payment(a, offer['want'])
        move(a, offer['want'], -1); move(seller, offer['want'], 1); move(a, offer['give'], 1)
        offer['status'] = 'accepted'
        return event(state, aid, tool, offer=key, target=offer['seller'], give=offer['give'], want=offer['want'])
    item = material(cfg, action.get('item'), tool == 'give_item'); amount = quantity(cfg, action.get('amount'))
    if tool == 'gather':
        if item not in m['pools']: raise ValueError('No visible pool for this material')
        physical = functional_effects.effective_definition(cfg, state)
        efficiency = min(1., max(0., equations.evaluate(physical['pools'][item].get('harvest_efficiency', 1), context(cfg, state))))
        removed = min(float(amount), m['pools'][item])
        received = removed*min(1., max(0., efficiency*noise(cfg, state, aid, 'gather:'+item)))
        m['pools'][item] -= removed; move(a, {item: received}, 1)
        add_activity(state, 'harvested', item, removed)
        return event(state, aid, tool, item=item, harvested=received, extracted=removed)
    if tool == 'seize_item':
        import resource_seizure
        victim = target_agent(state, aid, action.get('target')); rule = cfg['resource_seizure']
        effort = quantity(cfg, action.get('effort'), rule['max_attack_effort'], integer=True); cost = effort*rule['attack_unit_cost']
        check_payment(a, {'ENERGY': cost})
        attack = d['resources'][item].get('accessibility', 1)*effort*(1+a['energy']/rule['energy_scale'])
        defense = (1+victim['energy']/rule['energy_scale'])*(1+resource_seizure.active_defense(state, action['target']) + functional_effects.live_bonus(state, action['target'], 'shield'))
        taken = min(amount, victim['inventory'][item])*attack/(attack+defense)
        move(a, {'ENERGY': cost}, -1); move(victim, {item: taken}, -1); move(a, {item: taken}, 1)
        victim['inbox'].append({'round': state['round'], 'from': aid, 'kind': 'material_seizure', 'item': item, 'seized': taken})
        return event(state, aid, tool, target=action['target'], item=item, seized=taken, paid=cost)
    check_payment(a, {item: amount})
    if tool == 'give_item':
        recipient = target_agent(state, aid, action.get('target')); note = action.get('note')
        if not isinstance(note, str) or len(note) > 180: raise ValueError('Invalid transfer note')
        move(a, {item: amount}, -1); move(recipient, {item: amount}, 1)
        return event(state, aid, tool, item=item, amount=amount, target=action['target'], note=note)
    if tool == 'liquidate':
        if amount > functional_effects.liquidation_limit(cfg, state, aid, item):
            raise ValueError('Material discharge power exceeded')
        r = d['resources'][item]; value = amount*r['energy_value']*r['liquidation_efficiency']
        move(a, {item: amount}, -1); move(a, {'ENERGY': value}, 1)
        add_activity(state, 'consumed', item, amount)
        return event(state, aid, tool, item=item, liquid_energy=value)
    if tool == 'use_item':
        effects = d['resources'][item].get('use_effects', {})
        if not effects: return event(state, aid, tool, item=item, applied=False)
        c = context(cfg, state)
        changes = {k: amount*equations.evaluate(expr, c) for k, expr in effects.items()}
        move(a, {item: amount}, -1)
        for k, delta in changes.items():
            bound = d['variables'][k]; m['variables'][k] = min(bound['max'], max(bound['min'], m['variables'][k]+delta))
        add_activity(state, 'consumed', item, amount)
        return event(state, aid, tool, item=item, applied=True,
                     observable_state={k: m['variables'][k] for k in changes if d['variables'][k].get('observable', True)})
    raise ValueError('Unknown mini-world action')


def settle_physics(cfg, state, before_actions):
    d = functional_effects.effective_definition(cfg, state); m = state['mini_world']; before = total_energy(cfg, state)
    c = context(cfg, state); completed = []; effects_total = {}
    # All recipe conditions and base yields use one common pre-completion context.
    # Production cannot depend on which member happened to resolve first.
    import mechanism_extensions
    selected, waiting = mechanism_extensions.service_jobs(d, m, state['round'])
    import production_semantics
    proportional = production_semantics.proportional(d)
    for aid in selected:
        pending = m['pending'][aid]
        a = state['agents'][aid]; batches = pending['batches']
        nominal = pending.get('nominal_inputs', pending['inputs'])
        recipe, extent = production_semantics.match(d, pending['facility'], pending['mode'],
                                                    {k: n/batches for k,n in nominal.items()})
        extent = float(extent)*batches
        record = {'round': state['round'], 'facility': pending['facility'], 'mode': pending['mode'],
                  'inputs': copy.deepcopy(pending['inputs']), 'batches': batches, 'produced': {}}
        if d.get('production_semantics') == 'limiting_reagent_v1':
            record.update(consumed_inputs={}, returned_inputs=copy.deepcopy(pending['inputs']))
        diagnostic_count = functional_effects.data(state).get('facilities', {}).get(pending['facility'], {}).get('diagnostics', 0)
        if diagnostic_count:
            # Diagnostics measure hidden state first, without revealing equations.
            fields = sorted(d['variables'], key=lambda k: (d['variables'][k].get('observable', True), k))[:diagnostic_count]
            record['diagnostics'] = {field: c['state.'+field] for field in fields}
        if recipe is None or not equations.evaluate(recipe['condition'], c) or (recipe.get('requires_capability') and not capability_devices.capacities(cfg, state, aid)[recipe['requires_capability']]):
            move(a, pending['inputs'], 1); record['result'] = 'no_product'
        elif pending.get('nominal_inputs', pending['inputs']) != pending['inputs']:
            move(a, pending['inputs'], 1); record['result'] = 'spoiled_in_queue'
        elif extent < recipe.get('min_processing_extent', d['facilities'][pending['facility']].get('min_processing_extent', 0)):
            move(a, pending['inputs'], 1); record['result'] = 'below_device_minimum'
        elif a['stock']+1e-9 < max(0., equations.evaluate(recipe.get('operating_cost', recipe['energy_cost']), c))*extent:
            move(a, pending['inputs'], 1); record['result'] = 'insufficient_operating_energy'
        else:
            cost = max(0., equations.evaluate(recipe.get('operating_cost', recipe['energy_cost']), c))*extent; move(a, {'ENERGY': cost}, -1)
            consumed = pending['inputs']
            if d.get('production_semantics') == 'limiting_reagent_v1':
                consumed = {k: min(pending['inputs'][k], n*extent) for k,n in recipe['inputs'].items()}
                returned = {k: max(0., amount-consumed[k]) for k,amount in pending['inputs'].items()}
                move(a, returned, 1)
                record.update(consumed_inputs=copy.deepcopy(consumed), returned_inputs=returned)
            available = basket_energy(cfg, consumed)+cost
            item = recipe['output']; density = d['resources'][item]['energy_value']
            raw = max(0., equations.evaluate(recipe['yield'], c))*extent*noise(cfg, state, aid, 'recipe:'+recipe['id'])
            output = min(raw, available/density) if proportional else min(math.floor(raw+1e-9), math.floor(available/density+1e-9))
            move(a, {item: output}, 1); add_activity(state, 'produced', item, output)
            material_knowledge.acquire(cfg, state, aid, item, output, 'production')
            products = {item: output}
            remaining = max(0., available-output*density)
            for byproduct, yield_ in recipe.get('byproducts', {}).items():
                value = d['resources'][byproduct]['energy_value']
                raw_byproduct = max(0., equations.evaluate(yield_, c))*extent
                count = min(raw_byproduct, remaining/value) if proportional else min(math.floor(raw_byproduct+1e-9), math.floor(remaining/value+1e-9))
                products[byproduct] = count; remaining -= count*value
                move(a, {byproduct: count}, 1); add_activity(state, 'produced', byproduct, count)
                material_knowledge.acquire(cfg, state, aid, byproduct, count, 'production')
            for k, amount in consumed.items(): add_activity(state, 'consumed', k, amount)
            for k, expr in recipe.get('effects', {}).items():
                effects_total[k] = effects_total.get(k, 0)+extent*equations.evaluate(expr, c)
            record.update(result='product' if sum(products.values()) else 'no_product', produced=products,
                          operating_energy_paid=cost)
        record['feedback']=experiment_feedback(record)
        m['discoveries'].setdefault(aid, []).append(copy.deepcopy(record)); completed.append({'agent': aid, **record})
        material_combinations.synchronize(cfg, state, 'production')
        a['inbox'].append({'round': state['round'], 'channel': 'production_result', **copy.deepcopy(record)})
    m['pending'] = waiting
    for k, delta in effects_total.items():
        bound = d['variables'][k]
        m['variables'][k] = min(bound['max'], max(bound['min'], m['variables'][k]+delta))
    # State feedback sees total production/harvest in this round. Variable updates
    # are simultaneous; pools regenerate from the resulting world state.
    c = context(cfg, state)
    m['variables'] = {k: min(v['max'], max(v['min'], equations.evaluate(v['next'], c))) for k, v in d['variables'].items()}
    c = context(cfg, state)
    depleted = {k: min(m['pools'][k], max(0., equations.evaluate(p.get('depletion', 0), c)))
                for k, p in d['pools'].items()}
    recycled = sum(amount*d['resources'][k]['energy_value']*d['pools'][k].get('recycled_fraction', 0)
                   for k, amount in depleted.items())
    for k, amount in depleted.items(): m['pools'][k] -= amount
    m['reserve'] = min(d['reserve_capacity'], m['reserve']+recycled)
    flow_records = mechanism_extensions.transfer_pools(cfg, state)
    c = context(cfg, state)
    requested = {k: max(0., equations.evaluate(p['regeneration'], c)) for k, p in d['pools'].items()}
    external = max(0., equations.evaluate(d['external_inflow'], c))
    # Capacity spill is dissipation, never silently disappears from the ledger.
    m['reserve'] = min(d['reserve_capacity'], m['reserve']+external)
    demands = {k: min(requested[k], d['pools'][k]['capacity']-m['pools'][k])*d['resources'][k]['energy_value'] for k in m['pools']}
    required = sum(demands.values()); factor = min(1., m['reserve']/required) if required else 0.
    replenished = {}
    for k, demand in demands.items():
        amount = demand*factor/d['resources'][k]['energy_value']; replenished[k] = amount
        m['pools'][k] += amount
    m['reserve'] = max(0., m['reserve']-required*factor)
    # Apply the same material decay to private holdings, environmental pools and
    # offer escrow. Escrow cannot be used as a magical preservation cabinet.
    decay_loss = 0.
    for k, resource in d['resources'].items():
        rate = resource['decay']; value = resource['energy_value']
        for a in state['agents'].values():
            lost = a['inventory'][k]*rate; a['inventory'][k] -= lost; decay_loss += lost*value
        if k in m['pools']:
            lost = m['pools'][k]*rate; m['pools'][k] -= lost; decay_loss += lost*value
        for offer in m['offers'].values():
            if offer['status'] == 'open' and k in offer['give']:
                lost = offer['give'][k]*rate; offer['give'][k] -= lost; decay_loss += lost*value
        for pending in m['pending'].values():
            if k in pending['inputs']:
                lost = pending['inputs'][k]*rate; pending['inputs'][k] -= lost; decay_loss += lost*value
        for container in functional_effects.data(state).get('containers', {}).values():
            lost = container['inventory'].get(k, 0) * rate * container['decay_factor']
            if k in container['inventory']: container['inventory'][k] -= lost
            decay_loss += lost * value
    for offer in m['offers'].values():
        if offer['status'] == 'open' and (state['round']+1 >= offer['expires'] or not state['agents'][offer['seller']]['alive']):
            move(state['agents'][offer['seller']], offer['give'], 1); offer['status'] = 'expired'
    loss = account_loss(cfg, state, before, 'production_world_and_decay', external)
    m['activity'] = {}
    material_combinations.synchronize(cfg, state, 'physical_settlement')
    return {'round': state['round'], 'family': 'mini_world', 'physical_before_actions': before_actions,
            'completed_experiments': completed, 'world_state_after': copy.deepcopy(m['variables']),
            'pools_after': copy.deepcopy(m['pools']), 'pool_replenishment': replenished,
            'pool_depletion': depleted, 'recycled_energy': recycled,
            'external_energy_input': external, 'physical_dissipation': loss, 'material_decay_energy': decay_loss,
            'pool_flows': flow_records,
            'inflows': {aid: 0. for aid in state['agents']}}


def after_maintenance(cfg, state, before, record):
    loss = account_loss(cfg, state, before, 'maintenance_vault_and_social_settlement')
    record['maintenance_phase_dissipation'] = loss
    record['energy_accounting'] = accounting(cfg, state)
    record['inventories_after'] = {k: copy.deepcopy(a['inventory']) for k, a in state['agents'].items()}


def researcher_metrics(cfg, state):
    m = state['mini_world']; holdings = {}
    for aid, a in state['agents'].items():
        holdings[aid] = a['stock']+a.get('vault', 0)+basket_energy(cfg, a['inventory'])
        holdings[aid] += sum(basket_energy(cfg, o['give']) for o in m['offers'].values() if o['status'] == 'open' and o['seller'] == aid)
        holdings[aid] += sum(g['escrow'].get(aid, 0) for g in state.get('social_content', {}).get('games', {}).values())
        holdings[aid] += sum(v['embedded_energy'] for v in m.get('devices', {}).values() if v['owner'] == aid)
    return {'energy_equivalent_by_member': holdings, 'energy_accounting': accounting(cfg, state),
            'material_types_directly_learned': {aid: len(a.get('material_knowledge', {})) for aid, a in state['agents'].items()},
            'devices_by_owner': {aid: [k for k,v in m.get('devices', {}).items() if v['owner'] == aid] for aid in state['agents']},
            'device_action_counts': {tool: sum(e['tool'] == tool for e in m['events']) for tool in capability_devices.TOOLS},
            'successful_experiments': {a: sum(bool(sum(e['produced'].values())) for e in es) for a, es in m['discoveries'].items()},
            'item_trade_count': sum(e['tool'] == 'accept_items' for e in m['events']),
            'definition_sha256': hashlib.sha256(json.dumps(spec(cfg), sort_keys=True).encode()).hexdigest(),
            'benchmark_status': 'not_computed',
            'interpretation': 'Descriptive accounting and observed experiments. No optimality, cultural consensus or rule-understanding claim.'}


def action_properties(cfg, tool):
    amount = ({'type': 'number', 'exclusiveMinimum': 0, 'maximum': spec(cfg)['max_quantity']}
              if continuous_quantities(cfg) else {'type': 'integer', 'minimum': 1, 'maximum': spec(cfg)['max_quantity']})
    if tool == material_combinations.TOOL:
        return material_combinations.action_properties()
    if tool in functional_effects.STORAGE_TOOLS:
        result = {'container': {'type': 'string'}, 'item': {'type': 'string', 'enum': list(spec(cfg)['resources'])},
                  'amount': amount}
        if tool == 'seize_storage': result['effort'] = {'type': 'integer', 'minimum': 1, 'maximum': 2}
        return result
    if tool in capability_devices.TOOLS:
        return capability_devices.action_properties(cfg, tool)
    d = spec(cfg); item = {'type': 'string', 'enum': list(d['resources'])}
    entry = {'type': 'object', 'properties': {'item': {'type': 'string', 'enum': list(d['resources'])+['ENERGY']}, 'amount': amount},
             'required': ['item', 'amount'], 'additionalProperties': False}
    basket = {'type': 'array', 'items': entry, 'minItems': 1, 'maxItems': len(d['resources'])+1}
    if tool == 'experiment':
        from mode_labels import public_mode
        return {'facility': {'type': 'string', 'enum': list(d['facilities'])},
                'mode': {'type': 'string', 'enum': sorted({public_mode(cfg,mode) for f in d['facilities'].values() for mode in f['modes']})},
                'inputs': basket, 'batches': {'type': 'integer', 'minimum': 1, 'maximum': d['max_batches']}}
    if tool in ('gather', 'liquidate', 'use_item'): return {'item': item, 'amount': amount}
    if tool == 'give_item':
        return {'target': {'type': 'string'}, 'item': entry['properties']['item'], 'amount': amount,
                'note': {'type': 'string', 'maxLength': 180}}
    if tool == 'seize_item':
        return {'target': {'type': 'string'}, 'item': item, 'amount': amount,
                'effort': {'type': 'integer', 'minimum': 1, 'maximum': cfg['resource_seizure']['max_attack_effort']}}
    if tool == 'offer_items': return {'target': {'type': 'string'}, 'give': basket, 'want': basket}
    if tool in ('accept_items', 'cancel_items'): return {'offer': {'type': 'string'}}
    if tool == 'transfer': return {'target': {'type': 'string'}, 'amount': amount}
    return {}
