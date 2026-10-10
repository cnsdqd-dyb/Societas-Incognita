"""Versioned proportional production; fractional output lives in inventory."""
from fractions import Fraction
from functools import reduce
from math import gcd


def proportional(definition):
    return definition.get('production_semantics', 'exact_integer_v1') == 'proportional_v1'


def match(definition, facility, mode, basket):
    for recipe in definition['recipes']:
        if recipe['facility'] != facility or recipe['mode'] != mode:
            continue
        if set(recipe['inputs']) != set(basket):
            continue
        factors = [Fraction(str(basket[k])) / n for k, n in recipe['inputs'].items()]
        if proportional(definition):
            if factors[0] > 0 and all(x == factors[0] for x in factors):
                return recipe, factors[0]
        elif all(x == 1 for x in factors):
            return recipe, Fraction(1)
    return None, Fraction(0)


def normalize(definition):
    """Reduce input ratios, scaling every per-reaction extensive quantity."""
    for recipe in definition['recipes']:
        divisor = reduce(gcd, recipe['inputs'].values())
        if divisor == 1:
            continue
        recipe['inputs'] = {k: n // divisor for k, n in recipe['inputs'].items()}
        minimum = recipe.get('min_processing_extent',
                            definition['facilities'][recipe['facility']].get('min_processing_extent'))
        if minimum is not None:
            # Preserve the physical minimum when changing the reaction unit.
            recipe['min_processing_extent'] = minimum*divisor
        recipe['energy_cost'] /= divisor
        for name in ('yield', 'operating_cost'):
            if name in recipe:
                recipe[name] = {'op': 'div', 'args': [recipe[name], divisor]}
        for name in ('effects', 'byproducts'):
            recipe[name] = {k: {'op': 'div', 'args': [v, divisor]}
                            for k, v in recipe.get(name, {}).items()}
    definition['production_semantics'] = 'proportional_v1'
    return definition
