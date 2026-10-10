"""Possession-triggered private type knowledge, independent of world disclosure."""
import copy


def acquire(cfg, state, aid, item, amount, source):
    if amount <= 0 or item == 'ENERGY':
        return
    a = state['agents'][aid]
    known = a.setdefault('material_knowledge', {})
    if item in known:
        return
    r = cfg['world']['mini_world']['definition']['resources'][item]
    # Properties describe this material, never its production equation or recipe.
    properties = {k: copy.deepcopy(r[k]) for k in
                  ('energy_value', 'decay', 'liquidation_efficiency', 'tier', 'accessibility', 'traits', 'liquidation_limit') if k in r}
    properties['use_targets'] = sorted(r.get('use_effects', {}))
    known[item] = {'properties': properties, 'first_round': state['round'],
                   'source': source, 'evidence': 'direct_possession', 'version': 1}
    a['inbox'].append({'round': state['round'], 'channel': 'material_property_disclosure',
                       'item': item, 'source': source, 'version': 1})


def synchronize(cfg, state, source):
    for aid, a in state['agents'].items():
        for item, amount in a['inventory'].items():
            acquire(cfg, state, aid, item, amount, source)


def observe(state, aid):
    a = state['agents'][aid]
    return {k: {**copy.deepcopy(v), 'currently_held': a['inventory'].get(k, 0) > 0}
            for k, v in a.get('material_knowledge', {}).items()}
