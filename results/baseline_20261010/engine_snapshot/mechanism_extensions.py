"""Bounded material-flow and shared-facility extensions. No host-code execution."""
import copy

import world_rule_engine as e


def validate(d):
    refs = e.references(d)
    for r in d['resources'].values():
        if 'liquidation_limit' in r:
            if type(r['liquidation_limit']) is not int or not 1 <= r['liquidation_limit'] <= d['max_quantity']:
                raise ValueError('Invalid material discharge power')
    flows = d.get('pool_flows', [])
    if not isinstance(flows, list) or len(flows) > 128:
        raise ValueError('Invalid bounded pool flow graph')
    names = set()
    for f in flows:
        if f['id'] in names or f['source'] == f['target'] or any(f[k] not in d['pools'] for k in ('source', 'target')):
            raise ValueError('Invalid pool flow endpoints or identifier')
        names.add(f['id'])
        e.validate_expression(f['rate'], refs)
        e.number(f.get('efficiency', 1), 0, 1)
    for r in d['recipes']:
        byproducts = r.get('byproducts', {})
        if not isinstance(byproducts, dict) or len(byproducts) > 16 or r['output'] in byproducts:
            raise ValueError('Invalid byproducts')
        for item, yield_ in byproducts.items():
            if item not in d['resources']:
                raise ValueError('Unknown byproduct')
            e.validate_expression(yield_, refs)
        if 'operating_cost' in r:
            e.validate_expression(r['operating_cost'], refs)
    for f in d['facilities'].values():
        if 'service_capacity' in f:
            if type(f['service_capacity']) is not int or not 1 <= f['service_capacity'] <= 64:
                raise ValueError('Invalid facility service capacity')
            if type(f.get('switch_rounds', 0)) is not int or not 0 <= f.get('switch_rounds', 0) <= 100:
                raise ValueError('Invalid facility switching time')
    for field, bias in d.get('measurement_biases', {}).items():
        if field not in d['variables']:
            raise ValueError('Unknown biased field')
        e.validate_expression(bias, refs)


def transfer_pools(cfg, state):
    import mini_world as w
    d, m = w.spec(cfg), state['mini_world']
    context = w.context(cfg, state)
    requested = {f['id']: max(0., e.evaluate(f['rate'], context)) for f in d.get('pool_flows', [])}
    records = []
    # Rates share one pre-transfer observation; reservations resolve by declared order.
    for f in d.get('pool_flows', []):
        src, dst = f['source'], f['target']
        vs, vt = d['resources'][src]['energy_value'], d['resources'][dst]['energy_value']
        efficiency = f.get('efficiency', 1)
        received_per_unit = vs * efficiency / vt
        room = max(0., d['pools'][dst]['capacity'] - m['pools'][dst])
        moved = min(requested[f['id']], m['pools'][src], room / received_per_unit) if received_per_unit else 0.
        received = moved * received_per_unit
        m['pools'][src] -= moved
        m['pools'][dst] += received
        records.append({'id': f['id'], 'removed': moved, 'received': received,
                        'dissipated': moved * vs - received * vt})
    return records


def service_jobs(d, m, round_):
    """Select FIFO jobs, retaining unserved escrow and mode-switch downtime."""
    if not any('service_capacity' in f for f in d['facilities'].values()):
        return list(m['pending']), {}
    schedulers = m.setdefault('facility_schedulers', {})
    selected = []
    for name, f in d['facilities'].items():
        jobs = [(aid, p) for aid, p in m['pending'].items() if p['facility'] == name]
        jobs.sort(key=lambda x: (x[1].get('submitted_round', round_), x[0]))
        scheduler = schedulers.setdefault(name, {'mode': None, 'ready_round': 0})
        if not jobs or round_ < scheduler['ready_round']:
            continue
        mode = jobs[0][1]['mode']
        if scheduler['mode'] is not None and scheduler['mode'] != mode:
            scheduler['mode'] = mode
            scheduler['ready_round'] = round_ + f.get('switch_rounds', 0)
            if round_ < scheduler['ready_round']:
                continue
        scheduler['mode'] = mode
        same_mode = [aid for aid, p in jobs if p['mode'] == mode]
        selected.extend(same_mode[:f.get('service_capacity', 64)])
    # Keep immutable circuit-wire identities when this schedule is compiled for Lean.
    # No job payload is mutated during selection; the caller owns the returned jobs.
    waiting = {aid: dict(p) for aid, p in m['pending'].items() if aid not in selected}
    return selected, waiting
