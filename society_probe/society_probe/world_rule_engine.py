"""Bounded declarative world equations. No eval, imports or host code execution."""
import math

VERSION = 'mini_world_v1'
OPS = {'add', 'sub', 'mul', 'div', 'min', 'max', 'pow', 'exp', 'clamp',
       'lt', 'le', 'gt', 'ge', 'eq', 'and', 'or', 'not'}


def number(value, low=-1e9, high=1e9):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Expected bounded finite number')
    return value


def references(spec):
    refs = {'round', 'living', 'liquid_total'}
    refs |= {'state.'+k for k in spec['variables']}
    refs |= {'pool.'+k for k in spec['pools']}
    for prefix in ('produced', 'harvested', 'consumed'):
        refs |= {'activity.'+prefix+'.'+k for k in spec['resources']}
    refs |= {'activity.submitted.'+k for k in spec['facilities']}
    return refs


def validate_expression(expr, refs, depth=0, counter=None):
    counter = [0] if counter is None else counter
    counter[0] += 1
    if depth > 16 or counter[0] > 256:
        raise ValueError('Equation exceeds structural bound')
    if type(expr) in (int, float):
        number(expr)
        return
    if not isinstance(expr, dict):
        raise ValueError('Equations use constants, references and explicit operators')
    if set(expr) == {'ref'}:
        if expr['ref'] not in refs:
            raise ValueError('Unknown equation reference: '+str(expr['ref']))
        return
    if set(expr) != {'op', 'args'} or expr['op'] not in OPS or not isinstance(expr['args'], list):
        raise ValueError('Unknown equation operator')
    n = len(expr['args']); op = expr['op']
    if n > 16 or (op in ('exp', 'not') and n != 1) or (op == 'clamp' and n != 3):
        raise ValueError('Invalid equation arity')
    if op in ('sub', 'div', 'pow', 'lt', 'le', 'gt', 'ge', 'eq') and n != 2:
        raise ValueError('Invalid equation arity')
    if n < 1:
        raise ValueError('Empty equation')
    if op == 'pow' and (type(expr['args'][1]) is not int or not 0 <= expr['args'][1] <= 4):
        raise ValueError('Power must be a constant integer from 0 to 4')
    for arg in expr['args']:
        validate_expression(arg, refs, depth+1, counter)


def evaluate(expr, context):
    if type(expr) in (int, float):
        return number(expr)
    if 'ref' in expr:
        return number(context[expr['ref']])
    a = [evaluate(x, context) for x in expr['args']]; op = expr['op']
    if op == 'add': value = sum(a)
    elif op == 'sub': value = a[0]-a[1]
    elif op == 'mul': value = math.prod(a)
    elif op == 'div':
        if abs(a[1]) < 1e-12: raise ValueError('Zero equation denominator')
        value = a[0]/a[1]
    elif op == 'min': value = min(a)
    elif op == 'max': value = max(a)
    elif op == 'pow': value = a[0]**a[1]
    elif op == 'exp': value = math.exp(number(a[0], -50, 20))
    elif op == 'clamp':
        if a[1] > a[2]: raise ValueError('Reversed equation bounds')
        value = min(a[2], max(a[1], a[0]))
    elif op == 'lt': value = int(a[0] < a[1])
    elif op == 'le': value = int(a[0] <= a[1])
    elif op == 'gt': value = int(a[0] > a[1])
    elif op == 'ge': value = int(a[0] >= a[1])
    elif op == 'eq': value = int(a[0] == a[1])
    elif op == 'and': value = int(all(a))
    elif op == 'or': value = int(any(a))
    elif op == 'not': value = int(not a[0])
    else: raise ValueError('Unsupported equation')
    return number(value)


def validate(spec):
    if not isinstance(spec, dict) or spec.get('version') != VERSION:
        raise ValueError('Unsupported mini-world version')
    for name in ('resources', 'pools', 'variables', 'facilities'):
        if not isinstance(spec.get(name), dict) or len(spec[name]) > 64:
            raise ValueError('Invalid bounded world section: '+name)
    if not spec['resources'] or 'ENERGY' in spec['resources']:
        raise ValueError('Define materials; ENERGY is reserved for liquid energy')
    for section in ('resources', 'pools', 'variables', 'facilities'):
        for key in spec[section]:
            if not isinstance(key, str) or not key.isascii() or not key.replace('_', '').isalnum() or len(key) > 32:
                raise ValueError('World IDs must be short ASCII identifiers')
    refs = references(spec)
    for k, r in spec['resources'].items():
        number(r['energy_value'], 1e-6, 1e6)
        number(r['decay'], 0, 1)
        number(r['liquidation_efficiency'], 0, 1)
        number(r.get('accessibility', 1), 1e-6, 100)
        if type(r['tier']) is not int or not 0 <= r['tier'] <= 16:
            raise ValueError('Invalid resource tier')
        effects = r.get('use_effects', {})
        if not isinstance(effects, dict) or not set(effects) <= set(spec['variables']):
            raise ValueError('Unknown material function target')
        for expr in effects.values(): validate_expression(expr, refs)
    for k, p in spec['pools'].items():
        if k not in spec['resources']: raise ValueError('Unknown pool material')
        number(p['capacity'], 0, 1e6); number(p['initial'], 0, p['capacity'])
        validate_expression(p['regeneration'], refs)
        validate_expression(p.get('harvest_efficiency', 1), refs)
        validate_expression(p.get('depletion', 0), refs)
        number(p.get('recycled_fraction', 0), 0, 1)
    for v in spec['variables'].values():
        number(v['min']); number(v['max'], v['min']); number(v['initial'], v['min'], v['max'])
        validate_expression(v['next'], refs)
        if type(v.get('observable', True)) is not bool: raise ValueError('Invalid observability flag')
    for f in spec['facilities'].values():
        if not isinstance(f['modes'], list) or not 1 <= len(f['modes']) <= 16:
            raise ValueError('Invalid facility modes')
        if len(set(f['modes'])) != len(f['modes']) or any(not isinstance(m, str) or not 0 < len(m) <= 32 for m in f['modes']):
            raise ValueError('Invalid facility mode IDs')
    recipes = spec.get('recipes')
    if not isinstance(recipes, list) or len(recipes) > 128:
        raise ValueError('Invalid recipe graph')
    signatures = set(); ids = set()
    import production_semantics
    if spec.get('production_semantics', 'exact_integer_v1') not in ('exact_integer_v1', 'proportional_v1', 'limiting_reagent_v1'):
        raise ValueError('Unknown production semantics')
    for facility in spec['facilities'].values():
        number(facility.get('min_processing_extent', 0), 0, 1e6)
    for r in recipes:
        if not isinstance(r['id'], str) or r['id'] in ids: raise ValueError('Duplicate recipe ID')
        ids.add(r['id'])
        if r['facility'] not in spec['facilities'] or r['mode'] not in spec['facilities'][r['facility']]['modes']:
            raise ValueError('Unknown recipe station/mode')
        if r['output'] not in spec['resources'] or not r['inputs']:
            raise ValueError('Invalid recipe materials')
        for k, amount in r['inputs'].items():
            if k not in spec['resources'] or type(amount) is not int or not 1 <= amount <= 1000:
                raise ValueError('Invalid recipe input')
        signature = (r['facility'], r['mode'], tuple(sorted(r['inputs'].items())))
        if production_semantics.proportional(spec):
            from math import gcd
            from functools import reduce
            common = reduce(gcd, r['inputs'].values())
            signature = (r['facility'], r['mode'], tuple(sorted((k,n//common) for k,n in r['inputs'].items())))
        if spec.get('production_semantics') == 'limiting_reagent_v1':
            signature = (r['facility'], r['mode'], tuple(sorted(r['inputs'])))
        if signature in signatures: raise ValueError('Ambiguous recipe signature')
        signatures.add(signature)
        number(r['energy_cost'], 0, 1e6)
        number(r.get('min_processing_extent', 0), 0, 1e6)
        validate_expression(r['condition'], refs); validate_expression(r['yield'], refs)
        validate_expression(r.get('liquidation_modifier', 1), refs)
        effect = r.get('effects', {})
        if not set(effect) <= set(spec['variables']): raise ValueError('Unknown material function target')
        for expr in effect.values(): validate_expression(expr, refs)
    import property_rules
    property_rules.validate(spec)
    for k in ('initial_reserve', 'reserve_capacity', 'experiment_cost'):
        number(spec[k], 0, 1e9)
    if spec['initial_reserve'] > spec['reserve_capacity']: raise ValueError('Reserve exceeds capacity')
    validate_expression(spec['external_inflow'], refs)
    noise = spec['noise']
    if noise.get('distribution') not in ('none', 'uniform', 'triangular'):
        raise ValueError('Use bounded production noise')
    number(noise.get('amplitude', 0), 0, 1)
    for k in ('max_quantity', 'max_batches', 'max_offers', 'offer_ttl'):
        if type(spec[k]) is not int or not 1 <= spec[k] <= 10000:
            raise ValueError('Invalid interface bound: '+k)
    initial = spec.get('initial_inventory', {})
    if not set(initial) <= set(spec['resources']): raise ValueError('Unknown starting material')
    for amount in initial.values(): number(amount, 0, 1e6)
    for r in spec['resources'].values():
        traits = r.get('traits', [])
        if not isinstance(traits, list) or len(traits) > 16 or any(not isinstance(t, str) or len(t) > 256 for t in traits):
            raise ValueError('Material traits must be bounded descriptions')
    import capability_devices
    capability_devices.validate(spec)
    import mechanism_extensions
    mechanism_extensions.validate(spec)
    import material_combinations
    material_combinations.validate(spec)
    return spec


def definition(cfg):
    return cfg['world']['mini_world']['definition']
