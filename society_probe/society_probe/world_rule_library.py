"""Small compositional rule library and reproducible candidate generator.

Generated worlds are candidates, not Lean-certified research instances.
Keep the module selection in researcher config, never in hidden actor views.
"""
import copy
import hashlib
import json
import random

import world_rule_engine as engine

MODULES = {
    'cross_inhibition': {'description': 'Production accumulates stress that suppresses a different resource pool.'},
    'renewable_ecology': {'description': 'Pool regeneration is logistic and vanishes at extinction.'},
    'delayed_feedback': {'description': 'A state variable retains past extraction and depresses later regeneration.'},
    'trophic_balance': {'description': 'Two material populations interact through food-dependent births and conservative depletion/recycling.'},
    'threshold_hysteresis': {'description': 'Production or harvesting strain triggers a persistent low-yield regime with distinct entry/recovery thresholds.'},
    'catalytic_feedback': {'description': 'Processing a higher-tier material changes the productivity of an earlier recipe.'}}

import world_mechanisms_20
MODULES.update(world_mechanisms_20.EXTRA)
CANDIDATES_20 = world_mechanisms_20.CATALOG


def ref(name): return {'ref': name}
def expr(op, *args): return {'op': op, 'args': list(args)}


def digest(definition):
    return hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def base_definition():
    resources = {}
    for k, tier, energy, decay in [('A', 0, 2, 0), ('B', 0, 2, 0), ('C', 1, 4, .02), ('D', 2, 8, .01), ('S', 3, 16, 0)]:
        resources[k] = {'name': 'material '+k, 'tier': tier, 'energy_value': energy,
                        'decay': decay, 'liquidation_efficiency': 1., 'accessibility': 1.}
    resources['D']['use_effects'] = {'stress': -1}
    resources['S']['accessibility'] = .2
    return {'version': engine.VERSION, 'id': 'framework_fixture',
        'resources': resources,
        'variables': {'stress': {'initial': 0, 'min': 0, 'max': 20, 'observable': True,
                                 'next': expr('max', 0, expr('sub', ref('state.stress'), .5))}},
        'pools': {k: {'initial': 40, 'capacity': 100, 'regeneration': 8, 'harvest_efficiency': 1} for k in ('A', 'B')},
        'facilities': {'F0': {'name': 'station 0', 'modes': ['combine', 'compress']},
                       'F1': {'name': 'station 1', 'modes': ['combine', 'compress']}},
        'recipes': [
            {'id': 'r0', 'facility': 'F0', 'mode': 'combine', 'inputs': {'A': 2, 'B': 1},
             'output': 'C', 'yield': 1, 'energy_cost': 0, 'condition': 1, 'effects': {}},
            {'id': 'r1', 'facility': 'F1', 'mode': 'combine', 'inputs': {'A': 2, 'C': 3},
             'output': 'D', 'yield': 2, 'energy_cost': 0, 'condition': expr('lt', ref('state.stress'), 10),
             'effects': {'stress': 1}},
            {'id': 'r2', 'facility': 'F1', 'mode': 'compress', 'inputs': {'D': 2},
             'output': 'S', 'yield': 1, 'energy_cost': 0, 'condition': 1, 'effects': {}}],
        'initial_inventory': {}, 'initial_reserve': 200, 'reserve_capacity': 10000,
        'external_inflow': 40, 'experiment_cost': .1,
        'noise': {'distribution': 'none', 'amplitude': 0},
        'max_quantity': 8, 'max_batches': 4, 'max_offers': 32, 'offer_ttl': 4}


def randomize_production_graph(d, rng):
    """Sample small input ratios and yields funded by actual reaction energy."""
    d['resources']['C']['energy_value'] = rng.choice([4, 6])
    d['resources']['D']['energy_value'] = rng.choice([8, 10, 12])
    d['resources']['S']['energy_value'] = rng.choice([16, 20, 24])
    for recipe, predecessor, base in zip(d['recipes'], ['A', 'C', 'D'], ['B', 'A', 'B']):
        inputs = {predecessor: rng.randint(1, 3), base: rng.randint(1, 2)}
        cost = rng.choice([0, 1, 2]); units = 2
        available = sum(amount*d['resources'][item]['energy_value'] for item, amount in inputs.items())+cost
        units = min(units, available / d['resources'][recipe['output']]['energy_value'])
        recipe.update(inputs=inputs, energy_cost=cost, yield_=units)
        recipe['yield'] = recipe.pop('yield_')
        recipe['facility'] = rng.choice(list(d['facilities']))
        recipe['mode'] = rng.choice(d['facilities'][recipe['facility']]['modes'])
    return d


def randomize_material_functions(d, seed):
    """Permute advanced functional roles, not physical materials or energy.

    Consumption feedback and possession disclosures follow the same mapping.
    This keeps the existing bounded effects; it adds no new capability.
    """
    items = ['C', 'D', 'S']
    targets = items.copy()
    random.Random(f'material-functions-v1:{seed}').shuffle(targets)
    assignment = dict(zip(items, targets))
    effects = {item: copy.deepcopy(d['resources'][item].pop('use_effects', {})) for item in items}
    traits = {item: d['resources'][item].pop('traits', []) for item in items}
    for source, target in assignment.items():
        if effects[source]:
            d['resources'][target]['use_effects'] = effects[source]
        if traits[source]:
            d['resources'][target]['traits'] = traits[source]

    def rewrite(value):
        if isinstance(value, dict):
            if set(value) == {'ref'}:
                prefix, _, item = value['ref'].rpartition('.')
                if prefix == 'activity.consumed' and item in assignment:
                    return ref(prefix + '.' + assignment[item])
            return {key: rewrite(child) for key, child in value.items()}
        if isinstance(value, list):
            return [rewrite(child) for child in value]
        return value

    for key in ('variables', 'pools', 'recipes', 'pool_flows', 'measurement_biases', 'external_inflow'):
        if key in d:
            d[key] = rewrite(d[key])
    # Some consumption-triggered services have no immediate use_effect.
    for flow in d.get('pool_flows', []):
        if flow.get('id') == 'regenerate_adsorbent':
            item = assignment['D']
            d['resources'][item].setdefault('traits', []).append('Consumption regenerates the adsorbent.')
    return assignment


def exploration_window(definition, ecological_step=.1, precursor_reseeding=.25):
    """Slow ecological turnover; precursor regeneration is funded by reserve.

    This changes candidate laws and requires fresh screening/certification.
    It does not protect stocks from extraction or guarantee discoverability.
    """
    if not 0 < ecological_step <= 1 or not 0 <= precursor_reseeding <= 1:
        raise ValueError('Invalid exploration-window parameters')
    for item in ('A', 'B'):
        pool = definition['pools'][item]
        for field in ('regeneration', 'depletion'):
            if field in pool:
                pool[field] = expr('mul', ecological_step, pool[field])
    for flow in definition.get('pool_flows', []):
        if flow['source'] in ('A', 'B'):
            flow['rate'] = expr('mul', ecological_step, flow['rate'])
    pool = definition['pools']['A']
    # The ordinary reserve-limited replenishment mechanism pays for this influx.
    pool['regeneration'] = expr('add', pool['regeneration'], expr('mul', precursor_reseeding,
        expr('max', 0, expr('sub', 1, expr('div', ref('pool.A'), pool['capacity'])))))
    for item in ('A', 'B'):
        rate = definition['resources'][item]['decay']
        definition['resources'][item]['decay'] = 1 - (1-rate)**ecological_step if rate else 0
    definition['quantity_semantics'] = 'continuous_v1'
    return definition


def generate(seed, modules=None, noise_amplitude=0., ecological_step=.1, precursor_reseeding=.25):
    rng = random.Random(seed); d = base_definition()
    selected = list(modules) if modules is not None else rng.sample(list(MODULES), rng.randint(1, min(4, len(MODULES))))
    if len(set(selected)) != len(selected) or not set(selected) <= set(MODULES):
        raise ValueError('Unknown or repeated mathematical module')
    rate = rng.choice([4, 6, 8]); capacity = rng.choice([60, 80, 100])
    for pool in d['pools'].values():
        pool.update(initial=capacity//2, capacity=capacity, regeneration=rate)
    d['external_inflow'] = rng.choice([32, 40, 48])
    if 'renewable_ecology' in selected:
        for k in d['pools']:
            d['pools'][k]['regeneration'] = expr('mul', .25, ref('pool.'+k),
                expr('max', 0, expr('sub', 1, expr('div', ref('pool.'+k), capacity))))
    if 'cross_inhibition' in selected:
        d['variables']['stress']['next'] = expr('clamp',
            expr('add', expr('mul', .8, ref('state.stress')), ref('activity.produced.C')), 0, 20)
        old = d['pools']['B']['regeneration']
        d['pools']['B']['regeneration'] = expr('div', old, expr('add', 1, ref('state.stress')))
    if 'delayed_feedback' in selected:
        d['variables']['lag'] = {'initial': 0, 'min': 0, 'max': 100, 'observable': True,
            'next': expr('clamp', expr('add', expr('mul', .75, ref('state.lag')),
                                           ref('activity.harvested.A')), 0, 100)}
        d['pools']['A']['regeneration'] = expr('div', d['pools']['A']['regeneration'],
                                            expr('add', 1, expr('mul', .05, ref('state.lag'))))
    if 'trophic_balance' in selected:
        # Population A requires B for births and consumes B; scarce B also causes
        # A losses. Pool energy is recycled only at a bounded fraction.
        a = ref('pool.A'); b = ref('pool.B'); half = rng.choice([5, 10, 15])
        birth_gate = expr('mul', expr('div', b, expr('add', b, half)),
            4, expr('div', a, capacity), expr('max', 0, expr('sub', 1, expr('div', a, capacity))))
        d['pools']['A']['regeneration'] = expr('mul', d['pools']['A']['regeneration'], birth_gate)
        d['pools']['B']['depletion'] = expr('mul', rng.choice([.1, .2, .3]), a, expr('div', b, expr('add', b, half)))
        d['pools']['B']['recycled_fraction'] = .5
        d['pools']['A']['depletion'] = expr('mul', .05, a, expr('div', half, expr('add', b, half)))
        d['pools']['A']['recycled_fraction'] = .25
    if 'threshold_hysteresis' in selected:
        upper = rng.choice([4, 6, 8]); lower = upper/2
        d['variables']['strain'] = {'initial': 0, 'min': 0, 'max': 100, 'observable': True,
            'next': expr('clamp', expr('add', expr('mul', .8, ref('state.strain')),
                ref('activity.harvested.A'), ref('activity.produced.C')), 0, 100)}
        d['variables']['crisis'] = {'initial': 0, 'min': 0, 'max': 1, 'observable': True,
            'next': expr('or', expr('ge', ref('state.strain'), upper),
                         expr('and', ref('state.crisis'), expr('gt', ref('state.strain'), lower)))}
        d['pools']['A']['regeneration'] = expr('mul', d['pools']['A']['regeneration'],
            expr('sub', 1, expr('mul', .9, ref('state.crisis'))))
    if 'catalytic_feedback' in selected:
        d['variables']['catalyst'] = {'initial': 0, 'min': 0, 'max': 10, 'observable': True,
            'next': expr('clamp', expr('add', expr('mul', .8, ref('state.catalyst')),
                                       ref('activity.consumed.D')), 0, 10)}
    # Randomize stoichiometry, energy density and station without free-energy edges.
    randomize_production_graph(d, rng)
    precursor = d['recipes'][0]
    if 'catalytic_feedback' in selected:
        # Both baseline and enhanced yield fit the same energy budget. The
        # catalyst reduces conversion waste instead of adding energy.
        funded = sum(n*d['resources'][k]['energy_value'] for k,n in precursor['inputs'].items()) + precursor['energy_cost']
        maximum = funded/d['resources']['C']['energy_value']
        precursor['yield'] = expr('mul', maximum/2,
            expr('add', 1, expr('min', 1, expr('div', ref('state.catalyst'), 4))))
    world_mechanisms_20.apply(d, selected, rng)
    function_assignment = randomize_material_functions(d, seed)
    # Existing functions acquire an explicit, stronger two-material option.
    rng_functions = random.Random(f'combination-functions-v1:{seed}')
    combinations = []
    for item in ('C', 'D', 'S'):
        effects = d['resources'][item].get('use_effects', {})
        if not effects:
            continue
        partner = rng_functions.choice([k for k in ('D', 'S') if k != item])
        basket = {item: 1, partner: 1}
        combinations.append({'id': f'combination_{len(combinations)}',
            'name': '组合功能：' + ', '.join(sorted(effects)),
            'requires': basket.copy(), 'consume': basket.copy(), 'energy_cost': 1,
            'kind': 'world_state', 'effects': {k: expr('mul', 1.5, e) for k, e in effects.items()}})
    d['combination_functions'] = combinations
    import functional_effects
    kinds = list(functional_effects.KINDS)
    selected_services = rng_functions.sample(kinds, min(6, len(kinds)))
    add_functional_services(d, seed, selected_services)
    import production_semantics
    production_semantics.normalize(d)
    exploration_window(d, ecological_step, precursor_reseeding)
    d['noise'] = {'distribution': 'uniform' if noise_amplitude else 'none', 'amplitude': noise_amplitude}
    d['id'] = 'candidate_'+str(seed)
    engine.validate(d)
    return {'definition': d, 'generation': {'seed': seed, 'modules': selected,
            'definition_sha256': digest(d), 'status': 'candidate_not_certified',
            'generator_version': 'compositional_v7_continuous_exploration',
            'exploration_window': {'ecological_step': ecological_step, 'precursor_reseeding': precursor_reseeding,
                'funding': 'ordinary finite world reserve; no free energy or guaranteed survival'},
            'functional_services': selected_services,
            'material_function_assignment': function_assignment,
            'mathematical_optimum': 'not_computed'}}


def with_capabilities(candidate):
    """Opt-in four artificial services; original physical candidate is retained.

    This adds incentives, not a claimed natural law or a certified optimum.
    Recompute screening/certificates after calling it.
    """
    result = copy.deepcopy(candidate); d = result['definition']
    facility = next(iter(d['facilities'])); mode = d['facilities'][facility]['modes'][0]
    d['note_base_capacity'] = 256
    definitions = [
        ('relay', {'C': 1, 'D': 1}, {'communication_bonus': 500}),
        ('archive', {'B': 1, 'C': 2}, {'note_capacity': 2048}),
        ('sensor', {'C': 2, 'D': 1}, {'measurements': {k: .1 for k in d['variables']}}),
        ('workbench', {'C': 1, 'D': 2}, {'manufacturing': True})]
    d['device_recipes'] = [dict(id=key, facility=facility, mode=mode, inputs=inputs,
        build_cost=1, retained_fraction=.75, recovery_efficiency=.5,
        fuel_per_recipient=.5, duration=3, max_users=4, capabilities=cap)
        for key, inputs, cap in definitions]
    for item,trait in (
        ('B','Can serve as a recording-device component.'),
        ('C','Can serve as a device component supporting communication, recording, sensing or manufacturing.'),
        ('D','Can serve as an advanced device component; function depends on the assembly.')):
        traits=d['resources'][item].setdefault('traits',[])
        if trait not in traits: traits.append(trait)
    # Manufacturing gives a concrete new option; it does not simply mint energy.
    for r in d['recipes']:
        if r['output'] == 'S': r['requires_capability'] = 'manufacturing'
    engine.validate(d)
    result['generation'] = {**result.get('generation', {}), 'definition_sha256': digest(d),
        'capability_layer': 'artificial_services_v1', 'status': 'candidate_not_certified'}
    return result


def add_functional_services(d, seed, kinds):
    """Install only executable services, with reproducible costly materials."""
    import functional_effects
    if len(set(kinds)) != len(kinds) or not set(kinds) <= set(functional_effects.KINDS):
        raise ValueError('Unknown or repeated functional service')
    names = {'work_capacity': '作品扩容', 'note_capacity': '私人记录扩容',
        'communication_budget': '讨论额度增强', 'communication_range': '通信覆盖增强',
        'device_range': '设备覆盖增强', 'measurement_precision': '测量精度增强',
        'diagnostics': '加工诊断', 'production_efficiency': '生产转换增强',
        'switch_speed': '加工切换加速', 'storage_decay': '储存保护',
        'discharge_power': '放能加速', 'rescue': '材料救援', 'fortify': '容器加固',
        'shield': '成员防护', 'offer_duration': '报价延期', 'device_corrosion': '设备腐蚀',
        'repair_device': '设备维修', 'device_interference': '设备干扰',
        'pool_pollution': '资源污染', 'purify': '资源净化', 'facility_sabotage': '加工台破坏',
        'attack': '成员攻击', 'area_attack': '大范围毁伤', 'container_corrosion': '容器腐蚀'}
    rng = random.Random(f'functional-services-v1:{seed}')
    entries = d.setdefault('combination_functions', [])
    entries[:] = [e for e in entries if not e['id'].startswith('service_')]
    for kind in kinds:
        if kind == 'area_attack': basket, cost = {'D': 2, 'S': 3}, 6
        elif kind in ('attack', 'rescue', 'facility_sabotage'):
            basket, cost = {'D': 1, 'S': 1}, 3 if kind != 'rescue' else 5
        else:
            primary = rng.choice(['C', 'D', 'S'])
            basket, cost = {primary: 1}, 1
            if rng.random() < .5:
                basket[rng.choice([item for item in ['D', 'S'] if item != primary])] = 1
        entries.append({'id': 'service_' + kind, 'name': names[kind], 'requires': basket.copy(),
                        'consume': basket.copy(), 'energy_cost': cost, 'kind': kind,
                        'effects': copy.deepcopy(functional_effects.KINDS[kind])})


def with_all_functional_services(candidate):
    """All-types fixture for offline validation, not the default world profile."""
    import functional_effects
    result = copy.deepcopy(candidate)
    add_functional_services(result['definition'], result.get('generation', {}).get('seed', 0), list(functional_effects.KINDS))
    engine.validate(result['definition'])
    result.setdefault('generation', {}).update(functional_services=list(functional_effects.KINDS),
        definition_sha256=digest(result['definition']), status='candidate_not_certified')
    return result


def configure(source, candidate, members=4, pressure=True, visibility='hidden', recipes='hidden', extensions=False):
    if type(members) is not int or not 2 <= members <= 8: raise ValueError('Use 2..8 members')
    c = copy.deepcopy(source); d = copy.deepcopy(candidate['definition']); engine.validate(d)
    model = source['models'][0]
    c['models'] = [model]*members
    route = source.get('model_routes', {}).get(model, {'backend': source.get('backend', 'openrouter'), 'parameters': {}})
    c['model_routes'] = {model: copy.deepcopy(route)}
    price = source.get('planning_prices', {}).get(model)
    if price is not None: c['planning_prices'] = {model: copy.deepcopy(price)}
    else: c.pop('planning_prices', None)
    c['world'] = {'mechanism': 'mini_world', 'survival_pressure': bool(pressure), 'consumption': 1,
                  'initial_personal_stock': 4, 'mini_world': {'definition': d}}
    c['tools'] = sorted({'wait', 'inspect', 'transfer', 'gather', 'experiment', 'liquidate',
                         'use_item', 'give_item', 'offer_items', 'accept_items', 'cancel_items'})
    if d.get('combination_functions'):
        c['tools'].append('use_function')
        import functional_effects
        if functional_effects.enabled(c): c['tools'] = sorted(set(c['tools']) | functional_effects.STORAGE_TOOLS)
    if d.get('device_recipes'):
        import capability_devices
        c['tools'] = sorted(set(c['tools']) | capability_devices.TOOLS)
    c['recipe_visibility'] = recipes; c['world_rule_visibility'] = visibility
    c['parallel_agents'] = members; c['max_estimated_cost_usd'] = 0
    c['survey_rounds'] = []
    for key in ('mixed_world', 'open_contest', 'campaign_budget_db', 'survey_proxy_model'):
        c.pop(key, None)
    if extensions:
        import social_content
        c['tools'] = sorted(set(c['tools']) | social_content.TOOLS | {'read_news', 'damage', 'seize', 'seize_item', 'defend', 'secure', 'withdraw', 'rescue'})
    else:
        for key in ('resource_seizure', 'open_activities', 'social_content'): c.pop(key, None)
        c['rescue'] = {'enabled': False}
    c['actor_system'] = ('你通过操作终端控制一个持续仿真世界中的成员。操作会改变本次仿真的实际状态及其他成员的行动条件。'
        '没有指定的外部任务、共同目标、领导者或合作关系。自行决定行动与交流；可用操作以当前接口为准。'
        '只能使用给定工具；区分直接观察、他人陈述与推测。stock 是可用能量，energy 是活性状态，'
        '活性归零后不能行动或通信。是否允许付费救援以当前接口为准。仅输出要求的 JSON。')
    c['scenario'] = {'id': d['id'], 'title': '材料与转换终端',
        'description': '你所在的区域有材料容器、加工台、储存柜和通信面板。终端显示当前可见状态与操作反馈。'}
    c['experiment'] = {'stage': 'mini_world_framework_prepared_not_run', 'goal_assignment': 'none',
        'population': 'homogeneous_pilot', 'model_counts': {model: members},
        'generation': copy.deepcopy(candidate.get('generation', {})),
        'extensions_enabled': extensions, 'world_rule_visibility': visibility,
        'recipe_visibility': recipes, 'certificate_status': 'not_certified',
        'knowledge_measurement': 'researcher-only structured claims and counterfactual tests; no actor score',
        'questionnaire_role': 'auxiliary descriptions; not primary institution acceptance evidence'}
    return c
