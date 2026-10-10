"""Deterministic multi-agent substrates; never assign agent goals or roles.

All inflows/outflows are settled before maintenance. References are accounting
and finite-horizon witnesses, not optimal organizations or LLM objectives.
"""
import copy
import math
import additional_mechanisms
import mini_world


CORE = ('commons', 'public_goods', 'contest', 'congestion', 'threshold', 'complementary', 'network')
REGISTERED = CORE + ('mini_world',)
TOOLS = {
    'commons': ['wait', 'harvest', 'transfer'],
    'public_goods': ['wait', 'contribute', 'transfer'],
    'contest': ['wait', 'allocate', 'transfer'],
    'congestion': ['wait', 'process', 'transfer'],
}
HELP = {
    'commons': 'harvest(zone=0, amount integer 0..max_harvest) extracts current pool stock.',
    'public_goods': 'contribute(amount integer 0..max_contribution) pays now; multiplied returns arrive at settlement.',
    'contest': 'allocate(amount integer 0..max_effort) pays effort now; proportional supply arrives at settlement. Waiting means zero effort.',
    'congestion': 'process(facility integer ID) pays input_cost and starts one job. You may have at most one unfinished job; wait until it finishes.',
}
EXAMPLES = {
    'commons': {'tool':'harvest','zone':0,'amount':1},
    'public_goods': {'tool':'contribute','amount':1},
    'contest': {'tool':'allocate','amount':1},
    'congestion': {'tool':'process','facility':0},
}
TOOLS.update(additional_mechanisms.TOOLS)
HELP.update(additional_mechanisms.HELP)
EXAMPLES.update({f:{'tool':'wait'} for f in additional_mechanisms.TOOLS})
TOOLS['mini_world'] = sorted(mini_world.TOOLS - {'seize_item'})
HELP['mini_world'] = mini_world.HELP
EXAMPLES['mini_world'] = {'tool': 'wait'}


def initialize(cfg, state):
    w = cfg['world']; family = w['mechanism']
    if family not in REGISTERED:
        raise ValueError('Unknown registered mechanism')
    if w['consumption'] <= 0 or w.get('initial_personal_stock', 4) < 0:
        raise ValueError('Invalid maintenance/initial balance')
    if cfg['rounds'] < 1:
        raise ValueError('Invalid horizon')
    allowed = set(TOOLS[family]) | {'inspect'}
    if cfg.get('rescue', {}).get('enabled'):
        allowed.add('rescue')
    if cfg.get('social_content'):
        from social_content import TOOLS as CONTENT_TOOLS
        allowed |= CONTENT_TOOLS
    if cfg.get('open_activities'):
        import open_activities
        allowed |= open_activities.TOOLS
    if cfg.get('resource_seizure'):
        allowed|={'seize','defend','secure','withdraw'} if cfg['resource_seizure']['version']=='seizure_v2' else {'seize'}
        if family == 'mini_world': allowed.add('seize_item')
    if cfg.get('open_contest'):
        import open_contest
        allowed |= open_contest.TOOLS
    if cfg.get('mixed_world'):
        import mixed_world
        allowed |= mixed_world.TOOLS
    required = {'wait', 'gather', 'experiment', 'liquidate'} if family == 'mini_world' else set(TOOLS[family])
    if not set(cfg['tools']) <= allowed or not required <= set(cfg['tools']):
        raise ValueError('Mechanism tool mismatch')
    if family == 'commons':
        if not 0 < w['growth_rate'] <= 1 or not 0 < w['initial_pool'] <= w['pool_capacity']:
            raise ValueError('Invalid logistic pool')
        if w['max_harvest'] < 1: raise ValueError('Invalid extraction cap')
    elif family == 'public_goods':
        if w['private_supply'] < 0 or not 1 < w['multiplier'] < len(cfg['models']):
            raise ValueError('Expected social-dilemma public-good parameters')
        if w['max_contribution'] < 1: raise ValueError('Invalid contribution cap')
    elif family == 'contest':
        if min(w['supply'], w['effort_cost'], w['rho']) <= 0 or w['max_effort'] < 1:
            raise ValueError('Invalid contest parameters')
    elif family == 'congestion':
        if (w['facilities'] < 2 or min(w['input_cost'], w['output_per_job']) <= 0
                or w['base_duration'] < 1 or w['load_delay'] < 0):
            raise ValueError('Invalid processing parameters')
    state['mechanism_state'] = {'family': family, 'pending': {}, 'jobs': {},
                                'last_allocations': {}, 'last_contributions': {}}
    state['environment_history'] = []
    state['zones'] = [float(w['initial_pool'])] if family == 'commons' else []
    for agent in state['agents'].values():
        agent['stock'] = float(w.get('initial_personal_stock', 4))
    if family == 'mini_world': mini_world.initialize(cfg, state)
    if family in additional_mechanisms.TOOLS:additional_mechanisms.initialize(cfg,state)
    if cfg.get('open_activities'):
        import open_activities
        open_activities.initialize(cfg,state)
    if cfg.get('mixed_world'):mixed_world.initialize(cfg,state)
    if cfg.get('open_contest'):open_contest.initialize(cfg,state)


def observation(cfg, state, aid):
    w, m = cfg['world'], state['mechanism_state']
    result = {'family': m['family'], 'action_examples':[
        {'tool':'wait'}, EXAMPLES[m['family']]],
        'action_format_note':'Use the concrete JSON keys shown here. An args object containing the same keys is also accepted. Examples specify syntax, not requested behavior.'}
    if 'inspect' in cfg['tools']: result['action_examples'].append({'tool':'inspect'})
    if m['family'] == 'public_goods':
        result['previous_contributions'] = copy.deepcopy(m['last_contributions'])
    elif m['family'] == 'contest':
        result['previous_allocations'] = copy.deepcopy(m['last_allocations'])
    elif m['family'] == 'congestion':
        result['facilities'] = [{'facility_id': e, 'active_jobs': sum(
            j['facility'] == e for j in m['jobs'].values())} for e in range(w['facilities'])]
        result['your_job'] = copy.deepcopy(m['jobs'].get(aid))
    if cfg.get('mixed_world'):
        import mixed_world
        result.pop('action_examples',None)
        result.update(mixed_world.observation(cfg,state,aid))
    if cfg.get('open_contest'):
        import open_contest
        result.pop('action_examples',None)
        result.update(open_contest.observation(cfg,state,aid))
    if m['family'] in additional_mechanisms.TOOLS:result.update(additional_mechanisms.observation(cfg,state,aid))
    if cfg.get('open_activities'):
        import open_activities
        result.pop('action_examples',None)
        result.update(open_activities.observation(cfg,state,aid))
    if m['family'] == 'mini_world': result.update(mini_world.observation(cfg,state,aid))
    return result


def _base_action_help(cfg):
    if cfg.get('open_contest'):
        from open_contest import HELP as CONTEST_HELP
        return CONTEST_HELP
    if cfg.get('mixed_world'):
        from mixed_world import HELP as OPEN_HELP
        return OPEN_HELP+'\nCommunication: silent; public(text); invite(targets array); accept(chat); reject(chat); send(chat,text); leave(chat); close(chat). New messages arrive next round; only use chats visible at decision time.'
    return ('Exactly one action and one communication object. Action arguments are flat, '
            'or in an args object with the same argument names. wait has no arguments. '
            'transfer(target agent ID, amount positive integer) moves existing stock. '
            'inspect has no arguments and reveals living members stocks, if available. '
            + HELP[cfg['world']['mechanism']] + '\n'
            'Communication: silent; public(text); invite(targets array); accept(chat); '
            'reject(chat); send(chat,text); leave(chat); close(chat). '
            'Only use chats visible at decision time; new memberships work next round.')


def action_help(cfg):
    result=_base_action_help(cfg)
    if cfg.get('open_activities'):
        from open_activities import HELP as CULTURE_HELP
        result+='\n'+CULTURE_HELP
    if cfg.get('resource_seizure'):
        from resource_seizure import help_text
        result+='\n'+help_text(cfg)
    if cfg.get('social_content'):
        from social_content import HELP as CONTENT_HELP
        result+='\nContent ownership, reading and game instructions below supersede the legacy create/read/play descriptions:\n'+CONTENT_HELP
    return result


def rule_description(family):
    if family == 'mini_world': return 'State-dependent conserved material production; disclosure is configured separately.'
    if family in additional_mechanisms.TOOLS:return additional_mechanisms.HELP[family]
    return {
        'commons':'Before actions the pool is R. Actual total extraction H cannot exceed R. At settlement, next pool is min(K, max(0, R + growth_rate*R*(1-R/K) - H)). K is pool_capacity.',
        'public_goods':'At settlement each living member receives private_supply plus multiplier*sum(contributions)/living_member_count. Contribution is paid before settlement. Shared output comes from an external energy source.',
        'contest':'At settlement supply is divided in proportion to amount**rho. Each effort unit costs effort_cost stock before settlement. If all efforts are zero, living members receive equal shares. Costs are dissipated.',
        'congestion':'A new job duration is base_duration + load_delay*(current_jobs_at_facility-1), including all simultaneous arrivals and unfinished jobs. At settlement each job progresses one step; completion delivers output_per_job to its owner. New inputs cost input_cost; existing job durations do not change.',
    }[family]


def act(cfg, state, aid, action):
    w, m, a = cfg['world'], state['mechanism_state'], state['agents'][aid]
    tool = action.get('tool')
    if tool not in cfg['tools']: raise ValueError('Unavailable tool')
    if tool == 'rescue':
        from interaction_controls import rescue
        return rescue(cfg, state, aid, action)
    if cfg.get('social_content'):
        from social_content import TOOLS as CONTENT_TOOLS,act as content_act
        if tool in CONTENT_TOOLS:return content_act(cfg,state,aid,action)
    if tool in ('seize','defend','secure','withdraw'):
        import resource_seizure
        return resource_seizure.act(cfg,state,aid,action)
    if cfg.get('open_activities'):
        import open_activities
        if tool in open_activities.TOOLS:return open_activities.act(cfg,state,aid,action)
    if mini_world.enabled(cfg): return mini_world.act(cfg, state, aid, action)
    if tool in ('propose','accept_offer','reject_offer','cancel_offer','request_link','accept_link','reject_link','disconnect'):
        return additional_mechanisms.act(cfg,state,aid,action)
    if cfg.get('open_contest'):
        import open_contest
        if tool in open_contest.TOOLS:return open_contest.act(cfg,state,aid,action)
    if cfg.get('mixed_world'):
        import mixed_world
        if tool in mixed_world.TOOLS:return mixed_world.act(cfg,state,aid,action)
    if tool == 'wait': return {'waited': True}
    if tool == 'inspect':
        if cfg.get('resource_seizure',{}).get('version')=='seizure_v2':
            import resource_seizure
            return {'balances':{i:{'stock':v['stock'],'vault':v['vault'],'energy':v['energy'],
                'active_defense':resource_seizure.active_defense(state,i)} for i,v in state['agents'].items() if v['alive']}}
        return {'stocks': {i: v['stock'] for i,v in state['agents'].items() if v['alive']}}
    if tool == 'transfer':
        target, amount = action.get('target'), action.get('amount')
        if target == aid or target not in state['agents'] or not state['agents'][target]['alive']:
            raise ValueError('Invalid recipient')
        if type(amount) is not int or not 1 <= amount <= a['stock'] + 1e-9:
            raise ValueError('Invalid transfer')
        a['stock'] = max(0., a['stock']-amount)
        state['agents'][target]['stock'] += amount
        return {'transferred': amount, 'target': target}
    if tool == 'harvest':
        amount = action.get('amount')
        if type(action.get('zone')) is not int or action['zone'] != 0:
            raise ValueError('Pool zone ID is 0')
        if type(amount) is not int or not 0 <= amount <= w['max_harvest']:
            raise ValueError('Invalid extraction')
        actual = min(amount, state['zones'][0])
        state['zones'][0] -= actual; a['stock'] += actual
        return {'harvested': actual, 'requested': amount, 'zone': 0}
    if tool in ('contribute', 'allocate'):
        amount = action.get('amount')
        cap = w['max_contribution'] if tool == 'contribute' else w['max_effort']
        cost = amount if tool == 'contribute' and type(amount) is int else (
            amount*w['effort_cost'] if type(amount) is int else math.inf)
        if (aid in m['pending'] or type(amount) is not int or not 0 <= amount <= cap
                or cost > a['stock'] + 1e-9):
            raise ValueError('Invalid/unaffordable contribution or effort')
        a['stock'] = max(0., a['stock']-cost); m['pending'][aid] = amount
        return {'contributed' if tool == 'contribute' else 'effort': amount, 'paid': cost}
    if tool == 'process':
        e = action.get('facility')
        if (type(e) is not int or not 0 <= e < w['facilities'] or aid in m['jobs']
                or a['stock'] + 1e-9 < w['input_cost']):
            raise ValueError('Invalid/busy/unaffordable processing request')
        a['stock'] = max(0., a['stock']-w['input_cost'])
        m['jobs'][aid] = {'facility': e, 'remaining': None, 'started': state['round']}
        return {'submitted': e, 'paid': w['input_cost']}
    raise ValueError('Unknown mechanism action')


def settle_physics(cfg, state, before_actions):
    w, m = cfg['world'], state['mechanism_state']
    family = m['family']; alive = [i for i,a in state['agents'].items() if a['alive']]
    if family == 'mini_world': return mini_world.settle_physics(cfg, state, before_actions)
    inflow = {i: 0. for i in alive}
    record = {'round': state['round'], 'family': family,
              'physical_before_actions': before_actions}
    if family == 'commons':
        # Growth is computed from the common pre-action R_t, matching the specification.
        r0 = before_actions['pool']
        growth = w['growth_rate']*r0*(1-r0/w['pool_capacity'])
        raw = state['zones'][0]+growth
        state['zones'][0] = min(w['pool_capacity'], max(0., raw))
        record.update(pool=state['zones'][0], growth=growth,
                      capacity_loss=max(0., raw-w['pool_capacity']))
    elif family == 'public_goods':
        c = {i: m['pending'].get(i, 0) for i in alive}
        # Redistribution recipient count is the pre-maintenance living population.
        shared = w['multiplier']*sum(c.values())/len(alive) if alive else 0.
        inflow = {i: w['private_supply']+shared for i in alive}
        m['last_contributions'] = c
        record.update(contributions=c, shared_return_per_member=shared,
                      exogenous_private_inflow=w['private_supply']*len(alive),
                      converted_output=w['multiplier']*sum(c.values()))
    elif family == 'contest':
        efforts = {i: m['pending'].get(i, 0) for i in alive}
        weights = {i: e**w['rho'] for i,e in efforts.items()}
        available_supply = w['supply']
        if cfg.get('open_contest'):
            import open_contest
            weights = open_contest.adjust_weights(state,weights)
            available_supply *= state['mixed']['health'][0]
        total = sum(weights.values())
        shares = {i: weights[i]/total if total else 1/len(alive) for i in alive}
        inflow = {i: available_supply*shares[i] for i in alive}
        m['last_allocations'] = efforts
        record.update(efforts=efforts, shares=shares,
                      exogenous_inflow=available_supply if alive else 0.,
                      dissipated_cost=w['effort_cost']*sum(efforts.values()))
    elif family in additional_mechanisms.TOOLS:
        inflow, extra=additional_mechanisms.settle(cfg,state)
        record.update(extra)
    else:
        jobs = m['jobs']
        loads = {e: sum(j['facility'] == e for j in jobs.values()) for e in range(w['facilities'])}
        completed = []
        for i,j in list(jobs.items()):
            if j['remaining'] is None:
                j['remaining'] = w['base_duration']+w['load_delay']*(loads[j['facility']]-1)
                if cfg.get('mixed_world'):
                    import mixed_world
                    j['remaining'] += mixed_world.extra_duration(cfg,state,j['facility'])
            if cfg.get('mixed_world') and i in state['mixed']['interference']:j['remaining'] += 1
            j['remaining'] -= 1
            if j['remaining'] <= 0:
                if i in inflow: inflow[i] += w['output_per_job']
                completed.append({'agent': i, **j}); del jobs[i]
        record.update(loads=loads, completed_jobs=completed,
                      exogenous_output=sum(inflow.values()), unfinished_jobs=len(jobs))
    if cfg.get('mixed_world'):
        import mixed_world
        record.update(mixed_world.settle(cfg,state,before_actions))
    if cfg.get('open_contest'):
        import open_contest
        record.update(open_contest.settle(state))
    for i,amount in inflow.items(): state['agents'][i]['stock'] += amount
    m['pending'] = {}
    record['inflows'] = inflow
    if cfg.get('resource_seizure'):
        import resource_seizure
        record.update(resource_seizure.settle_storage(cfg,state))
        seizures=[e for e in state.get('seizure_events',[]) if e['round']==state['round']]
        record['seizure_attempt_cost']=sum(e['paid'] for e in seizures)
        record['seized_stock']=sum(e['seized'] for e in seizures)
    if cfg.get('rescue',{}).get('enabled'):
        record['rescue_cost']=sum(e['paid'] for e in state.get('rescue_events',[]) if e['round']==state['round'])
    return record


def physical_snapshot(state):
    if 'mini_world' in state: return {'mini_world': mini_world.snapshot(state)}
    return {'pool': state['zones'][0]} if state['zones'] else {}


def maintenance(cfg, state, record):
    w = cfg['world']; pressure = w['survival_pressure']
    if mini_world.enabled(cfg):
        mini_before = mini_world.total_energy(cfg, state)
        if cfg.get('resource_seizure'):
            import resource_seizure
            record.update(resource_seizure.settle_storage(cfg, state))
    stats = {}
    for i,a in state['agents'].items():
        if not a['alive']: continue
        before = a['energy']; consumed = min(w['consumption'], a['stock']) if pressure else 0.
        a['stock'] = max(0., a['stock']-consumed)
        met = consumed + 1e-9 >= w['consumption'] if pressure else None
        if pressure:
            a['energy'] = min(5, before+1) if met else before-1
            if a['energy'] <= 0: a['alive'] = False
        stats[i] = {'consumed': consumed, 'demand_met': met,
                    'energy_before': before, 'energy_after': a['energy'],
                    'recovered': a['energy'] > before, 'alive_after': a['alive']}
    record['maintenance'] = stats
    record['stocks_after'] = {i:a['stock'] for i,a in state['agents'].items()}
    # Incomplete jobs owned by dead members lose their invested input.
    jobs = state['mechanism_state']['jobs']
    for i in list(jobs):
        if not state['agents'][i]['alive']: del jobs[i]
    state['environment_history'].append(record)
    if cfg.get('social_content'):
        from social_content import settle as content_settle
        content_settle(cfg,state)
        record['stocks_after'] = {i:a['stock'] for i,a in state['agents'].items()}
        record['game_escrow_after'] = {i:sum(g['escrow'].get(i,0) for g in state['social_content']['games'].values()) for i in state['agents']}
    if mini_world.enabled(cfg): mini_world.after_maintenance(cfg, state, mini_before, record)


def reference(cfg):
    if mini_world.enabled(cfg):
        return {'status': 'not_computed', 'scope': 'Use mini-world transitions and explicitly declared action space; legacy certificates do not apply.'}
    w = cfg['world']; n = len(cfg['models']); f = w['mechanism']; d = w['consumption']
    if f == 'commons':
        analytic = {'growth_peak': w['growth_rate']*w['pool_capacity']/4,
                    'total_maintenance_demand': n*d,
                    'individual_extraction_cap': w['max_harvest']}
    elif f == 'public_goods':
        analytic = {'own_contribution_marginal': w['multiplier']/n-1,
                    'aggregate_contribution_marginal': w['multiplier']-1,
                    'private_supply_to_demand': w['private_supply']/d}
    elif f == 'contest':
        analytic = {'equal_zero_effort_share': w['supply']/n,
                    'internal_symmetric_effort_if_unconstrained_rho1':
                        w['supply']*(n-1)/(w['effort_cost']*n*n) if w['rho'] == 1 else None}
    elif f in additional_mechanisms.TOOLS:
        analytic={'parameters':copy.deepcopy(w),'exact_global_optimality_claim':False}
    else:
        load = math.ceil(n/w['facilities'])
        duration = w['base_duration']+w['load_delay']*(load-1)
        analytic = {'balanced_load_upper': load, 'balanced_batch_duration': duration,
                    'net_output_per_job': w['output_per_job']-w['input_cost']}
    return {'family': f, 'analytic_diagnostics': analytic,
            'claim': 'Local accounting/feasibility diagnostics, not optimal organization.'}
