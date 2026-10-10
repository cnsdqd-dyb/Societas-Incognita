"""Twenty candidate mechanisms as bounded discrete worlds, not natural simulators.

Ports are material pools, recipe yield/cost/condition, facility service and sensor
readout. Auxiliary control fields carry no physical energy; real stores use pools.
"""
import copy


CATALOG = (
    ('renewable_ecology', '存量依赖再生'), ('allee_threshold', '低存量阈值'),
    ('trophic_balance', '消费者资源制衡'), ('internal_quota', '内部物质配额'),
    ('substrate_inhibition', '底物过量抑制'), ('cross_feeding', '副产物互供'),
    ('competitive_catalysis', '专一催化与竞争抑制'), ('autocatalytic_seed', '自催化启动'),
    ('bistable_toggle', '互抑双稳态'), ('explicit_delay', '显式延迟管线'),
    ('chaotic_modulation', '确定性非线性调制'), ('reaction_diffusion', '三节点反应扩散'),
    ('congested_transport', '双路线拥堵'), ('shared_queue', '共享设施排队换线'),
    ('fatigue_repair', '累积损伤维修'), ('finite_adsorption', '有限吸附再生'),
    ('finite_buffer', '有限缓冲'), ('power_limited_storage', '容量功率受限储存'),
    ('conductance_network', '三节点串联导通'), ('calibrated_measurement', '测量偏差校准'))

EXTRA = {key: {'description': title, 'candidate_number': i, 'implementation': 'bounded_discrete_v1'}
         for i, (key, title) in enumerate(CATALOG, 1) if key not in ('renewable_ecology', 'trophic_balance')}


def ref(key): return {'ref': key}
def op(name, *args): return {'op': name, 'args': list(args)}


def multiply(*args):
    flat = []
    for a in args:
        flat.extend(a['args'] if isinstance(a, dict) and a.get('op') == 'mul' else [a])
    # The equation interpreter caps operator arity at sixteen.
    if len(flat) > 16:
        return op('mul', op('mul', *flat[:16]), *flat[16:])
    return op('mul', *flat)


def apply(d, selected, rng):
    def variable(name, initial, low, high, next_, observable=True):
        d['variables'][name] = {'initial': initial, 'min': low, 'max': high,
                                 'next': next_, 'observable': observable}
        return ref('state.' + name)

    def resource(name, value=2, initial=0, capacity=20):
        d['resources'][name] = {'name': 'material ' + name, 'tier': 1, 'energy_value': value,
            'decay': 0, 'liquidation_efficiency': 1., 'accessibility': 1.}
        d['pools'][name] = {'initial': initial, 'capacity': capacity, 'regeneration': 0, 'harvest_efficiency': 1}
        return ref('pool.' + name)

    def flow(name, source, target, rate, efficiency=1):
        d.setdefault('pool_flows', []).append({'id': name, 'source': source, 'target': target,
                                              'rate': rate, 'efficiency': efficiency})

    def gate(recipe, factor):
        recipe['yield'] = multiply(recipe['yield'], factor)

    def effect(item, name, amount):
        d['resources'][item].setdefault('use_effects', {})[name] = amount
        d['resources'][item].setdefault('traits', []).append('Using this material affects ' + name + '.')

    first = d['recipes'][0]
    if 'allee_threshold' in selected:
        threshold = rng.choice([6, 8, 10])
        for name in ('A', 'B'):
            pool = ref('pool.' + name)
            baseline = d['pools'][name]['regeneration'] if 'renewable_ecology' in selected or 'trophic_balance' in selected else multiply(.08, pool, op('sub', 1, op('div', pool, d['pools'][name]['capacity'])))
            signed = multiply(baseline, op('sub', op('div', pool, threshold), 1))
            d['pools'][name]['regeneration'] = op('max', 0, signed)
            d['pools'][name]['depletion'] = op('add', d['pools'][name].get('depletion', 0), op('max', 0, op('sub', 0, signed)))
    if 'internal_quota' in selected:
        quota = resource('Q', initial=6, capacity=16)
        flow('quota_loading', 'A', 'Q', op('div', ref('pool.A'), op('add', 10, ref('pool.A'))))
        d['pools']['Q']['depletion'] = multiply(.5, ref('activity.produced.C'))
        gate(first, op('max', 0, op('sub', 1, op('div', 2, op('max', 2, quota)))))
    if 'substrate_inhibition' in selected:
        # A fixed-volume station's retained substrate concentration, not all agents' wealth.
        substrate = variable('substrate', 1, 0, 100, op('clamp', op('add', multiply(.5, ref('state.substrate')),
                               ref('activity.consumed.A')), 0, 100))
        gate(first, op('div', multiply(4, substrate), op('add', 1, substrate, op('div', op('pow', substrate, 2), 4))))
    if 'cross_feeding' in selected:
        resource('W', value=1, capacity=0)
        first['byproducts'] = {'W': 2}
        d['recipes'][1].update(inputs={'C': 4, 'W': 4}, yield_=2, energy_cost=4)
        d['recipes'][1]['yield'] = d['recipes'][1].pop('yield_')
        d['resources']['W']['traits'] = ['A production byproduct usable by a different conversion process.']
    if 'competitive_catalysis' in selected:
        catalyst = variable('enzyme', 1, 0, 4, op('clamp', op('add', multiply(.95, ref('state.enzyme')),
                                                   ref('activity.consumed.D')), 0, 4))
        inhibitor = variable('inhibitor', 0, 0, 20, op('clamp', op('add', multiply(.8, ref('state.inhibitor')),
                                        ref('activity.harvested.B')), 0, 20))
        gate(first, op('div', multiply(2, catalyst), op('add', 1, catalyst, inhibitor)))
        effect('D', 'enzyme', 1)
    if 'autocatalytic_seed' in selected:
        # Seed is a real input, returned as part of the product; additional A funds growth.
        d['facilities']['F0']['modes'].append('seed')
        d['recipes'].append({'id': 'autocatalysis', 'facility': 'F0', 'mode': 'seed',
            'inputs': {'A': 2, 'C': 1}, 'output': 'C',
            'yield': 1+4/d['resources']['C']['energy_value'], 'energy_cost': 0,
            'condition': 1, 'effects': {}})
    if 'bistable_toggle' in selected:
        x = variable('toggle_x', 2, 0, 4, op('clamp', op('add', multiply(.8, ref('state.toggle_x')),
                  op('div', .6, op('add', 1, op('pow', ref('state.toggle_y'), 2)))), 0, 4))
        y = variable('toggle_y', .1, 0, 4, op('clamp', op('add', multiply(.8, ref('state.toggle_y')),
                  op('div', .6, op('add', 1, op('pow', ref('state.toggle_x'), 2)))), 0, 4))
        gate(first, op('div', op('add', 1, x), op('add', 2, x, y)))
        effect('D', 'toggle_y', 2)
    if 'explicit_delay' in selected:
        variable('delay_0', 0, 0, 100, ref('activity.harvested.A'))
        variable('delay_1', 0, 0, 100, ref('state.delay_0'))
        delayed = variable('delay_2', 0, 0, 100, ref('state.delay_1'))
        d['pools']['A']['regeneration'] = op('div', d['pools']['A']['regeneration'], op('add', 1, multiply(.1, delayed)))
    if 'chaotic_modulation' in selected:
        z = variable('chaos_z', .231, 0, 1, multiply(4, ref('state.chaos_z'), op('sub', 1, ref('state.chaos_z'))))
        d['pools']['B']['regeneration'] = multiply(d['pools']['B']['regeneration'], op('add', .2, multiply(.8, z)))
    if 'reaction_diffusion' in selected:
        # Dimensionless reaction-control fields at three actual production sites.
        for i in range(3):
            neighbors = [j for j in (i-1, i+1) if 0 <= j < 3]
            x, y = ref(f'state.rd_x{i}'), ref(f'state.rd_y{i}')
            for species, own, other, diffusivity in (('x', x, y, .1), ('y', y, x, .025)):
                diff = op('add', *[op('sub', ref(f'state.rd_{species}{j}'), own) for j in neighbors])
                variable(f'rd_{species}{i}', .2 + i*.1 if species == 'x' else .2, 0, 4,
                    op('clamp', op('add', own, multiply(.1, op('sub', op('div', 1, op('add', 1, op('pow', other, 2))), own)),
                                       multiply(diffusivity, diff)), 0, 4))
        for r in d['recipes']:
            site = 0 if r['facility'] == 'F0' else 2
            gate(r, op('div', 1, op('add', 1, ref(f'state.rd_y{site}'))))
    if 'congested_transport' in selected:
        # Two alternative routes to the same production process, chosen by station.
        originals = copy.deepcopy(d['recipes'])
        for r in originals:
            alternate = copy.deepcopy(r)
            alternate['id'] += '_route'
            alternate['facility'] = 'F1' if r['facility'] == 'F0' else 'F0'
            modes = d['facilities'][alternate['facility']]['modes']
            if alternate['mode'] not in modes:
                modes.append(alternate['mode'])
            signature = lambda a: (a['facility'], a['mode'], tuple(sorted(a['inputs'].items())))
            if not any(signature(a) == signature(alternate) for a in d['recipes']):
                d['recipes'].append(alternate)
        for r in d['recipes']:
            r['operating_cost'] = op('add', r['energy_cost'], .2,
                                     multiply(.3, ref('activity.submitted.' + r['facility'])))
    if 'shared_queue' in selected:
        for f in d['facilities'].values():
            f.update(service_capacity=1, switch_rounds=1)
    if 'fatigue_repair' in selected:
        damage = variable('damage', 0, 0, 2, op('clamp', op('add', ref('state.damage'),
                                       multiply(.1, ref('activity.produced.C'))), 0, 2))
        for r in d['recipes']:
            r['condition'] = op('and', r['condition'], op('lt', damage, 1))
        effect('D', 'damage', -.5)
    if 'finite_adsorption' in selected:
        pollutant = resource('P', value=1, initial=10, capacity=20)
        bound = resource('P_bound', value=1, capacity=8)
        flow('adsorb', 'P', 'P_bound', multiply(op('max', 0, op('sub', 8, bound)),
                                                op('div', pollutant, op('add', 2, pollutant))))
        flow('regenerate_adsorbent', 'P_bound', 'P', ref('activity.consumed.D'))
        gate(first, op('div', 1, op('add', 1, multiply(.1, pollutant))))
    if 'finite_buffer' in selected:
        if 'P' not in d['pools']:
            resource('P', value=1, initial=10, capacity=20)
        resource('P_neutral', value=1, capacity=100)
        cap = variable('buffer_capacity', 8, 0, 8, op('max', 0, op('sub', ref('state.buffer_capacity'),
                                              op('min', ref('pool.P'), ref('state.buffer_capacity')))))
        applied = variable('buffer_applied', 0, 0, 8, op('min', ref('pool.P'), ref('state.buffer_capacity')))
        flow('neutralize', 'P', 'P_neutral', applied)
        effect('D', 'buffer_capacity', 2)
        if 'finite_adsorption' not in selected:
            gate(first, op('div', 1, op('add', 1, multiply(.1, ref('pool.P')))))
    if 'power_limited_storage' in selected:
        storage = resource('BAT', initial=0, capacity=20)
        phase = variable('storage_phase', 0, 0, 1, op('sub', 1, ref('state.storage_phase')))
        flow('charge', 'A', 'BAT', multiply(2, phase), .9)
        flow('discharge', 'BAT', 'A', op('sub', 1, phase), .9)
        d['resources']['A']['decay'] = max(d['resources']['A']['decay'], .04)
        d['resources']['BAT']['liquidation_limit'] = 1
        d['resources']['BAT']['traits'] = ['Stable storage; capacity and charging/discharging power are separately bounded.']
    if 'conductance_network' in selected:
        resource('NET', capacity=20)
        g1 = variable('conductance_1', 1, 0, 1, ref('state.conductance_1'))
        g2 = variable('conductance_2', 0, 0, 1, ref('state.conductance_2'))
        effective = op('div', multiply(g1, g2), op('max', .000001, op('add', g1, g2)))
        flow('conduct', 'A', 'NET', multiply(4, effective))
        effect('D', 'conductance_2', 1)
        gate(first, op('add', .5, effective))
    if 'calibrated_measurement' in selected:
        calibrated = variable('calibration', 0, 0, 1, ref('state.calibration'), observable=False)
        d['measurement_biases'] = {'stress': multiply(.4, op('sub', 1, calibrated))}
        effect('C', 'calibration', 1)
    d.setdefault('mechanism_implementations', {}).update({key: 'bounded_discrete_v1' for key in selected if key in EXTRA})
    return d
