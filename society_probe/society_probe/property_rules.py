"""Finite propositional reaction rules, compiled to the existing physical engine.

Observations are rendered from the same facts used by the compiler. This is a
bounded consistency check over the declared world, not a Lean theorem or a
guarantee that agents can discover a rule in time.
"""
import copy
import itertools
import random

VERSION = 'property_rules_v1'
MAX_BINDINGS = 20000


def truth(formula, facts):
    if not isinstance(formula, dict) or len(formula) != 1:
        raise ValueError('Invalid property formula')
    op, args = next(iter(formula.items()))
    if op in ('and', 'or'):
        if not isinstance(args, list) or not 1 <= len(args) <= 16:
            raise ValueError('Invalid logical connective')
        values = [truth(x, facts) for x in args]
        return all(values) if op == 'and' else any(values)
    if op == 'not':
        return not truth(args, facts)
    if op == 'eq' and isinstance(args, list) and len(args) == 2:
        if args[0] not in facts:
            raise ValueError('Unknown property: ' + str(args[0]))
        return facts[args[0]] == args[1]
    raise ValueError('Unsupported property formula')


def refresh(d):
    """Recompile after an explicit researcher edit; validation never repairs it."""
    d['recipes'], report = compile_rules(d)
    for facility, f in d['facilities'].items():
        for mode in f['modes']:
            f['mode_properties'][mode]['sample_responses'] = [
                [copy.deepcopy(d['resources'][k]['observable_properties']) for k in r['inputs']]
                for r in d['recipes'] if r['facility'] == facility and r['mode'] == mode]
    return report


def signature(properties, prefix):
    """A DNF with two physically different ways to satisfy the same input role."""
    band = {'eq': [prefix + '.band', properties['band']]}
    direction = properties['direction']
    if direction == 0:
        return {'and': [band, {'eq': [prefix + '.direction', 0]},
                        {'eq': [prefix + '.porous', True]}]}
    return {'and': [band, {'or': [
        {'eq': [prefix + '.direction', direction]},
        {'and': [{'eq': [prefix + '.direction', 0]},
                 {'eq': [prefix + '.porous', True]}]}]}]}


def compile_rules(d):
    rules = d['property_rules']
    if rules.get('version') != VERSION:
        raise ValueError('Unknown property rule version')
    resources = d['resources']
    for r in resources.values():
        p = r.get('observable_properties', {})
        if set(p) != {'band', 'direction', 'porous'} or type(p['band']) is not int or not 0 <= p['band'] <= 128:
            raise ValueError('Invalid observable material properties')
        if type(p['direction']) is not int or p['direction'] not in (-1, 0, 1) or type(p['porous']) is not bool:
            raise ValueError('Invalid material probe response')
    compiled = []
    seen = set()
    checked = 0
    ids = set()
    for f in d['facilities'].values():
        if set(f.get('mode_properties', {})) != set(f['modes']):
            raise ValueError('Device mode properties are incomplete')
        for p in f['mode_properties'].values():
            if type(p.get('channel')) is not int or not 0 <= p['channel'] <= 100000:
                raise ValueError('Invalid device channel property')
    for rule in rules['reactions']:
        if rule['id'] in ids:
            raise ValueError('Duplicate logical reaction')
        ids.add(rule['id'])
        slots = rule['slots']
        if not 1 <= len(slots) <= 4 or any(type(n) is not int or n <= 0 for n in slots):
            raise ValueError('Invalid reaction slots')
        rule_matches = 0
        # Exhaustive over declared materials, devices and modes. We reject
        # overlap even when hidden continuous guards might be exclusive.
        for facility, f in d['facilities'].items():
            for mode in f['modes']:
                profile = f['mode_properties'][mode]
                for assignment in itertools.permutations(resources, len(slots)):
                    checked += 1
                    if checked > MAX_BINDINGS:
                        raise ValueError('Property world exceeds bounded compilation limit')
                    facts = {'device.channel': profile['channel']}
                    for i, item in enumerate(assignment):
                        facts.update({f'slot{i}.'+k: v for k,v in resources[item]['observable_properties'].items()})
                    if not truth(rule['when'], facts):
                        continue
                    rule_matches += 1
                    basket = dict(zip(assignment, slots))
                    key = (facility, mode, tuple(sorted(basket)))
                    if key in seen:
                        raise ValueError('Conflicting property reactions for ' + str(key))
                    seen.add(key)
                    recipe = copy.deepcopy(rule['then'])
                    recipe.update(id='pr'+str(len(compiled)), facility=facility, mode=mode,
                                  inputs=basket, property_rule_id=rule['id'])
                    compiled.append(recipe)
                    if len(compiled) > 128:
                        raise ValueError('Too many compiled property reactions')
        if not rule_matches:
            raise ValueError('Unsatisfiable logical reaction: ' + rule['id'])
    if not compiled:
        raise ValueError('Property world has no executable reactions')
    return compiled, {'status': 'finite_domain_checked', 'bindings_checked': checked,
                      'reactions': len(compiled), 'scope': 'Declared materials and device modes; overlapping structural antecedents rejected regardless of state guard'}


def validate(d):
    if not d.get('property_rules'):
        return
    compiled, _ = compile_rules(d)
    if compiled != d['recipes']:
        raise ValueError('Logical rules and executable reaction graph disagree')
    if d.get('production_semantics') != 'limiting_reagent_v1':
        raise ValueError('Property worlds require limiting-reagent processing')
    for facility, f in d['facilities'].items():
        for mode in f['modes']:
            expected = [[copy.deepcopy(d['resources'][k]['observable_properties']) for k in r['inputs']]
                        for r in compiled if r['facility'] == facility and r['mode'] == mode]
            if f['mode_properties'][mode].get('sample_responses') != expected:
                raise ValueError('Device observation and physical response disagree')


def install(definition, seed):
    d = copy.deepcopy(definition)
    if d.get('property_rules'):
        raise ValueError('Property rule layer is already installed')
    rng = random.Random('property-world-v1:' + str(seed))
    bands = rng.sample(range(1, 33), 4)
    directions = rng.choice([-1, 1])
    core = {'A': (bands[0], directions), 'B': (bands[0], -directions),
            'C': (bands[1], directions), 'W': (bands[1], -directions),
            'D': (bands[2], directions), 'S': (bands[3], directions)}
    for i, (item, resource) in enumerate(d['resources'].items()):
        band, direction = core.get(item, (40+i, rng.choice([-1, 1])))
        resource['observable_properties'] = {'band': band, 'direction': direction, 'porous': False}
    # A channel is a measurable equipment setting, not a requested action.
    channels = {}
    for facility, f in d['facilities'].items():
        f['mode_properties'] = {}
        for mode in f['modes']:
            channel = rng.randrange(100, 10000)
            while channel in channels.values():
                channel = rng.randrange(100, 10000)
            channels[facility, mode] = channel
            f['mode_properties'][mode] = {'channel': channel}
    reactions = []
    for r in d['recipes']:
        clauses = [{'eq': ['device.channel', channels[r['facility'], r['mode']]]}]
        slots = []
        for i, (item, amount) in enumerate(r['inputs'].items()):
            clauses.append(signature(d['resources'][item]['observable_properties'], 'slot'+str(i)))
            slots.append(amount)
        conclusion = {k: copy.deepcopy(v) for k,v in r.items() if k not in ('id','facility','mode','inputs')}
        reactions.append({'id': r['id'], 'slots': slots, 'when': {'and': clauses}, 'then': conclusion})
    d['property_rules'] = {'version': VERSION, 'reactions': reactions}
    d['production_semantics'] = 'limiting_reagent_v1'
    report = refresh(d)
    # Device observations show their physical input response, but never ratios,
    # output identities, guards, productivity equations, or function unlocks.
    return d, report


def material_description(p):
    direction = {-1: '左侧', 0: '中线', 1: '右侧'}[p['direction']]
    texture = '液滴会进入表面的细孔' if p['porous'] else '液滴停留在表面，未进入细孔'
    return f"光学探头在第{p['band']}格出现窄峰；悬置样片在标准场中偏向{direction}；{texture}。"


def observe(d, state, result):
    if not d.get('property_rules'):
        return result
    # Initial environmental specimens provide grounded observations without
    # disclosing possession-gated functional abilities.
    for material in result['material_catalog']:
        if state['mini_world']['pools'].get(material['item'], 0) > 0:
            material['sample_observation'] = material_description(d['resources'][material['item']]['observable_properties'])
    for station in result['stations']:
        station['observations'] = []
        for mode in station['modes']:
            p = d['facilities'][station['facility']]['mode_properties'][mode]
            samples = [' / '.join(material_description(x) for x in group) for group in p.get('sample_responses', [])]
            station['observations'].append({'mode': mode, 'description':
                f"面板通道读数为{p['channel']}。" + ('该设置的探测窗留有以下校准样片记录：'+'；'.join(samples) if samples else '探测窗没有样片记录。')})
    result['world_observations'] = [
        {'field': k, 'description': f"{k}探头本轮读数为{v:.8g}。"}
        for k,v in result.pop('world_state', {}).items()]
    for item, entry in result['your_material_knowledge'].items():
        original = entry.pop('properties', {})
        r = d['resources'][item]
        entry['observations'] = [material_description(r['observable_properties']),
            f"单位样本完全放能的标定值为{r['energy_value']:.8g}；每轮样本损失比例标定为{r['decay']:.8g}。"]
        entry['observations'].extend(original.get('traits', []))
        entry['available_use_targets'] = original.get('use_targets', [])
    result['processing_interface'] = '输入允许小数；可反应的部分按实际限制性原料结算，未反应材料返还。批次数为正整数。实际反应取决于材料、加工设置及当时状态；描述是观测记录，不是规律解释。'
    return result
